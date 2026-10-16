-- checks for customers: dupes, spaces, future dates. run with psql -f tests/dq/customers.sql
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
                "customer_id"
            FROM
                public.customers
            GROUP BY
                "customer_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'customers: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'customers dupes ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY[
        'first_name',
        'last_name',
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
                public.customers
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
            RAISE EXCEPTION 'customers: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'customers spaces ok';

    -- no null pks
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.customers
        WHERE
            "customer_id" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'customers: % null pk rows', n;
    END IF;
    RAISE NOTICE 'customers nulls ok';

    -- emails look like emails, zips stay 5-digit
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.customers
        WHERE
            "email" IS NOT NULL
            AND "email" !~ ''^[^@\s]+@[^@\s]+\.[^@\s]+$''
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'customers: % bad emails', n;
    END IF;
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.customers
        WHERE
            "zip_code" IS NOT NULL
            AND LENGTH("zip_code"::TEXT) <> 5
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'customers: % bad zips', n;
    END IF;
    RAISE NOTICE 'customers format ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.customers
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'customers: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'customers dates ok';
END $$;
