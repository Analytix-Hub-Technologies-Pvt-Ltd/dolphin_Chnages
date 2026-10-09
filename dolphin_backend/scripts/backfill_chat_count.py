"""Install chat-count maintenance and backfill one explicitly selected database.

Dry run is the default. Production writes require a separate explicit flag.
Connection secrets are loaded from --env-file and never included in reports.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import asyncpg
from dotenv import dotenv_values


def count_chats(history):
    if isinstance(history, str):
        try:
            history = json.loads(history)
        except ValueError:
            return None
    if not isinstance(history, list):
        return None
    waiting, count = False, 0
    for item in history:
        if not isinstance(item, dict):
            return None
        role = item.get('role')
        if role == 'user' or (role is None and 'question' in item):
            waiting = True
        if role == 'assistant':
            answer = item.get('content')
        elif role is None and 'response' in item:
            answer = item['response']
        else:
            continue
        has_answer = isinstance(answer, str) and bool(answer.strip())
        if isinstance(answer, dict):
            content = answer.get('content')
            quiz = answer.get('quiz_items')
            has_answer = (isinstance(content, str) and bool(content.strip())) or (isinstance(quiz, list) and bool(quiz))
        if waiting and has_answer:
            count += 1
            waiting = False
    return count


def metadata_object(raw):
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def validate_target(database, apply, allow_production=False):
    if database not in {'dolphintest', 'dolphindb'}:
        raise ValueError('Only dolphintest and dolphindb are supported')
    if database == 'dolphindb' and apply and not allow_production:
        raise ValueError('Production writes require --allow-production after verification')


async def backfill(conn, *, apply=False, batch_size=100, after=None):
    report = dict(scanned=0, updated=0, would_update=0, unchanged=0, skipped=0, concurrent_changes=0, completed_chats=0, last_session_id=after)
    while True:
        rows = await conn.fetch(
            'SELECT session_id, messages, metadata FROM public.chat_sessions '
            'WHERE ($1::text IS NULL OR session_id > $1) ORDER BY session_id LIMIT $2',
            after, batch_size,
        )
        if not rows:
            break
        # One transaction per batch. Conditional updates protect concurrent writes.
        async with conn.transaction():
            for row in rows:
                report['scanned'] += 1
                count = count_chats(row['messages'])
                metadata = metadata_object(row['metadata'])
                if count is None or metadata is None:
                    report['skipped'] += 1
                    print(json.dumps({'skipped_session_id': row['session_id'], 'reason': 'Invalid messages or metadata shape'}))
                    continue
                report['completed_chats'] += count
                if type(metadata.get('chat_count')) is int and metadata['chat_count'] == count:
                    report['unchanged'] += 1
                    continue
                if not apply:
                    report['would_update'] += 1
                    continue
                result = await conn.execute(
                    "UPDATE public.chat_sessions SET metadata = COALESCE(metadata, '{}'::jsonb) || "
                    "jsonb_build_object('chat_count', $2::integer) WHERE session_id=$1 "
                    "AND messages IS NOT DISTINCT FROM $3::jsonb AND metadata IS NOT DISTINCT FROM $4::jsonb",
                    row['session_id'], count, row['messages'], row['metadata'],
                )
                report['updated' if result == 'UPDATE 1' else 'concurrent_changes'] += 1
        after = rows[-1]['session_id']
        report['last_session_id'] = after
        if apply:
            print(json.dumps({'batch_committed': True, **report}))
    return report


async def install(conn):
    async with conn.transaction():
        await conn.execute("SET LOCAL lock_timeout = '5s'")
        await conn.execute(Path(__file__).with_name('chat_count.sql').read_text(encoding='utf-8'))
        await conn.execute('DROP TRIGGER IF EXISTS chat_sessions_sync_chat_count ON public.chat_sessions')
        await conn.execute('CREATE TRIGGER chat_sessions_sync_chat_count BEFORE INSERT OR UPDATE OF messages '
                           'ON public.chat_sessions FOR EACH ROW EXECUTE FUNCTION public.sync_session_chat_count()')


async def run(args):
    validate_target(args.database, args.apply, args.allow_production)
    env = dotenv_values(args.env_file)
    conn = await asyncpg.connect(
        host=env.get('DB_HOST', 'localhost'), port=int(env.get('DB_PORT', 5432)),
        user=env.get('DB_USER', 'postgres'), password=env.get('DB_PASSWORD'),
        database=args.database, timeout=15, command_timeout=60,
    )
    try:
        actual = await conn.fetchval('SELECT current_database()')
        if actual != args.database:
            raise RuntimeError('Connected database does not match requested target')
        print(json.dumps({'database': actual, 'mode': 'apply' if args.apply else 'dry-run'}))
        # Prevent overlapping invocations of this migration; no database data is changed.
        if not await conn.fetchval('SELECT pg_try_advisory_lock(917203601)'):
            raise RuntimeError('Another chat-count backfill is running')
        if args.apply:
            await install(conn)
            report = await backfill(conn, apply=True, batch_size=args.batch_size, after=args.after)
        else:
            async with conn.transaction(readonly=True):
                report = await backfill(conn, batch_size=args.batch_size, after=args.after)
        if args.apply:
            report['mismatched_counts'] = await conn.fetchval(
                "SELECT count(*) FROM public.chat_sessions WHERE public.count_session_chats(messages) IS NOT NULL "
                "AND (metadata->'chat_count') IS DISTINCT FROM to_jsonb(public.count_session_chats(messages))"
            )
        print(json.dumps({'database': actual, **report}))
        return 2 if report['skipped'] or report['concurrent_changes'] or report.get('mismatched_counts') else 0
    finally:
        await conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True, choices=['dolphintest', 'dolphindb'])
    p.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--allow-production', action='store_true')
    p.add_argument('--batch-size', type=int, default=100)
    p.add_argument('--after', help='Resume after a committed session ID; omit to safely rerun everything')
    args = p.parse_args()
    if not 1 <= args.batch_size <= 1000:
        p.error('--batch-size must be between 1 and 1000')
    try:
        return asyncio.run(run(args))
    except Exception as exc:
        # Avoid leaking connection credentials through exception details.
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'database': args.database}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
