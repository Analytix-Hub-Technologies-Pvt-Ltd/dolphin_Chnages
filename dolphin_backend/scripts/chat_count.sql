-- Count completed exchanges in persisted history, never increment on retries.
CREATE OR REPLACE FUNCTION public.count_session_chats(history jsonb)
RETURNS integer LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    item jsonb;
    answer jsonb;
    waiting boolean := false;
    result integer := 0;
    role_name text;
BEGIN
    IF history IS NULL OR jsonb_typeof(history) <> 'array' THEN RETURN NULL; END IF;
    FOR item IN SELECT value FROM jsonb_array_elements(history) LOOP
        IF jsonb_typeof(item) <> 'object' THEN RETURN NULL; END IF;
        role_name := item->>'role';
        IF role_name = 'user' OR (role_name IS NULL AND item ? 'question') THEN
            waiting := true;
        END IF;
        IF role_name = 'assistant' THEN
            answer := item->'content';
        ELSIF role_name IS NULL AND item ? 'response' THEN
            answer := item->'response';
        ELSE
            CONTINUE;
        END IF;
        -- Quiz answers can have structured content instead of plain text.
        IF waiting AND (
            (jsonb_typeof(answer) = 'string' AND (answer #>> '{}') ~ '[^[:space:]]')
            OR (jsonb_typeof(answer) = 'object' AND (
                (jsonb_typeof(answer->'content') = 'string' AND (answer->>'content') ~ '[^[:space:]]')
                OR (jsonb_typeof(answer->'quiz_items') = 'array' AND answer->'quiz_items' <> '[]'::jsonb)
            ))
        ) THEN
            result := result + 1;
            waiting := false;
        END IF;
    END LOOP;
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.sync_session_chat_count()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Do not silently destroy malformed non-object metadata.
    IF NEW.metadata IS NOT NULL AND jsonb_typeof(NEW.metadata) <> 'object' THEN
        RAISE EXCEPTION 'chat_sessions.metadata must be an object';
    END IF;
    NEW.metadata := COALESCE(NEW.metadata, '{}'::jsonb) ||
        jsonb_build_object('chat_count', public.count_session_chats(NEW.messages));
    RETURN NEW;
END;
$$;
