import asyncio
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest

spec = importlib.util.spec_from_file_location('backfill_chat_count', Path(__file__).resolve().parents[1] / 'scripts/backfill_chat_count.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

@pytest.mark.parametrize('history,expected', [
    ([], 0), (None, None), ({}, None), ('bad json', None), ([None], None),
    ([{'role':'user','content':'Question'}], 0),
    ([{'role':'assistant','content':'orphan'}], 0),
    ([{'role':'user'}, {'role':'assistant','content':'  \n'}], 0),
    ([{'role':'user'}, {'role':'assistant','content':'Answer'}], 1),
    ([{'role':'user'}, {'role':'assistant','content':'Answer'}, {'role':'assistant','content':'retry'}], 1),
    ([{'role':'user'}, {'role':'user'}, {'role':'assistant','content':'Answer'}], 1),
    ([{'role':'user'}, {'role':'assistant','content':'Answer'}, {'role':'user'}, {'role':'assistant','content':'Next'}], 2),
    ([{'question':'Question'}, {'response':'Answer'}], 1),
    ([{'question':'Question','response':'Answer'}], 1),
    ([{'role':'user'}, {'role':'assistant','content':{'type':'quiz','quiz_items':[{'q':'test'}]}}], 1),
    ([{'role':'user'}, {'role':'assistant','content':{}}], 0),
    ([{'role':'user'}, {'role':'system','content':'internal'}, {'role':'assistant','content':'Answer'}], 1),
])
def test_count(history, expected):
    assert module.count_chats(history) == expected


def test_production_requires_explicit_permission():
    with pytest.raises(ValueError):
        module.validate_target('dolphindb', True)
    module.validate_target('dolphintest', True)
    module.validate_target('dolphindb', False)
    with pytest.raises(ValueError):
        module.validate_target('other', True, True)

class Transaction:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass

class Connection:
    def __init__(self, rows, result='UPDATE 1'):
        self.fetch = AsyncMock(side_effect=[rows, []])
        self.execute = AsyncMock(return_value=result)
    def transaction(self): return Transaction()


def record(metadata='{}', messages=None):
    return {'session_id':'s1', 'messages': json.dumps(messages if messages is not None else [{'role':'user'}, {'role':'assistant','content':'Answer'}]), 'metadata':metadata}


def test_dry_run_does_not_update():
    c=Connection([record()])
    result=asyncio.run(module.backfill(c))
    assert result['would_update']==1
    c.execute.assert_not_awaited()


def test_preserve_other_metadata_and_protect_concurrent_updates():
    c=Connection([record('{"custom":"value"}')], 'UPDATE 0')
    result=asyncio.run(module.backfill(c, apply=True))
    assert result['concurrent_changes']==1
    sql, sid, count, messages, metadata=c.execute.await_args.args
    assert 'metadata = COALESCE(metadata' in sql
    assert 'messages IS NOT DISTINCT FROM' in sql
    assert 'metadata IS NOT DISTINCT FROM' in sql
    assert 'updated_at' not in sql
    assert count==1 and json.loads(metadata)=={'custom':'value'}


def test_rerun_skips_already_correct_count():
    c=Connection([record('{"chat_count":1}')])
    result=asyncio.run(module.backfill(c, apply=True))
    assert result['unchanged']==1
    c.execute.assert_not_awaited()


def test_invalid_history_does_not_become_zero():
    row=record(); row['messages']='{}'
    c=Connection([row])
    result=asyncio.run(module.backfill(c, apply=True))
    assert result['skipped']==1
    c.execute.assert_not_awaited()
