-- checks for stores: dupes, spaces, future dates. run with psql -f tests/dq/stores.sql
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
                "store_id"
            FROM
                public.stores
            GROUP BY
                "store_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stores: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'stores dupes ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY[
        'store_name',
        'phone',
        'email',
        'street',
        'city',
        'state'
    ] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.stores
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
            RAISE EXCEPTION 'stores: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'stores spaces ok';

    -- no null pks or names
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.stores
        WHERE
            "store_id" IS NULL
            OR "store_name" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stores: % null key/name rows', n;
    END IF;
    RAISE NOTICE 'stores nulls ok';

    -- emails look like emails, zips stay 5-digit
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.stores
        WHERE
            "email" IS NOT NULL
            AND "email" !~ ''^[^@\s]+@[^@\s]+\.[^@\s]+$''
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stores: % bad emails', n;
    END IF;
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.stores
        WHERE
            "zip_code" IS NOT NULL
            AND LENGTH("zip_code"::TEXT) <> 5
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'stores: % bad zips', n;
    END IF;
    RAISE NOTICE 'stores format ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.stores
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'stores: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'stores dates ok';
END $$;
