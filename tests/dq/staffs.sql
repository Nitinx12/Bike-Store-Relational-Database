-- checks for staffs: dupes, orphans, spaces, future dates. run with psql -f tests/dq/staffs.sql
DO $$
DECLARE
    n BIGINT;
    c TEXT;
    i INT;
    child_cols TEXT[] := ARRAY[
        'store_id',
        'manager_id'
    ];
    ref_tbls TEXT[] := ARRAY[
        'stores',
        'staffs'
    ];
    ref_cols TEXT[] := ARRAY[
        'store_id',
        'staff_id'
    ];
BEGIN
    -- duplicate pk rows
    EXECUTE '
        SELECT
            COUNT(*)
        FROM (
            SELECT
                "staff_id"
            FROM
                public.staffs
            GROUP BY
                "staff_id"
            HAVING
                COUNT(*) > 1
        ) AS d
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'staffs: % duplicate pk groups', n;
    END IF;
    RAISE NOTICE 'staffs dupes ok';

    -- orphan fk rows (manager_id is nullable, only set values must match)
    FOR i IN 1 .. array_length(child_cols, 1) LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.staffs AS c
            LEFT JOIN
                public.%I AS r
                ON r.%I = c.%I
            WHERE
                c.%I IS NOT NULL
                AND r.%I IS NULL',
            ref_tbls[i],
            ref_cols[i],
            child_cols[i],
            child_cols[i],
            ref_cols[i]
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'staffs: % orphan rows on % -> %.%',
                n, child_cols[i], ref_tbls[i], ref_cols[i];
        END IF;
    END LOOP;
    RAISE NOTICE 'staffs orphans ok';

    -- leading/trailing/double spaces or empty strings in text cols
    FOREACH c IN ARRAY ARRAY[
        'first_name',
        'last_name',
        'email',
        'phone'
    ] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.staffs
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
            RAISE EXCEPTION 'staffs: %-space rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'staffs spaces ok';

    -- no null pks
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.staffs
        WHERE
            "staff_id" IS NULL
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'staffs: % null pk rows', n;
    END IF;
    RAISE NOTICE 'staffs nulls ok';

    -- emails look like emails, nobody manages themselves, active is 0/1
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.staffs
        WHERE
            "email" IS NOT NULL
            AND "email" !~ ''^[^@\s]+@[^@\s]+\.[^@\s]+$''
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'staffs: % bad emails', n;
    END IF;
    EXECUTE '
        SELECT
            COUNT(*)
        FROM
            public.staffs
        WHERE
            "manager_id" = "staff_id"
            OR ("active" IS NOT NULL AND "active" NOT IN (0, 1))
    ' INTO n;
    IF n > 0 THEN
        RAISE EXCEPTION 'staffs: % bad manager/active rows', n;
    END IF;
    RAISE NOTICE 'staffs format ok';

    -- future timestamps
    FOREACH c IN ARRAY ARRAY['updated_at'] LOOP
        EXECUTE format(
            'SELECT
                COUNT(*)
            FROM
                public.staffs
            WHERE
                %I > now()',
            c
        ) INTO n;
        IF n > 0 THEN
            RAISE EXCEPTION 'staffs: % future rows in %', n, c;
        END IF;
    END LOOP;
    RAISE NOTICE 'staffs dates ok';
END $$;
