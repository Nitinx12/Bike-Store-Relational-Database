-- checks for categories: dupes, spaces, future dates. run with psql -f tests/dq/categories.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
BEGIN
    -- duplicate pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "category_id"
            FROM
                public.categories
            GROUP BY
                "category_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'categories: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'categories dupes ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY['category_name'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.categories
            WHERE
                %I IS NOT NULL
                AND (
                    %I <> btrim(%I)
                    OR %I = ''''
                    OR strpos(%I, ''  '') > 0
                )',
            c, c, c, c, c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'categories: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'categories spaces ok';

    -- no null pks or names
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.categories
        WHERE
            "category_id" IS NULL
            OR "category_name" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'categories: % null key/name rows', n;
    END IF;
    RAISE NOTICE 'categories nulls ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.categories
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'categories: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'categories dates ok';
END $$;
