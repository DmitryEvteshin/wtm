# pylint: disable=too-many-lines

from aiomysql import Connection

async def get_operator_tasks_table(conn: Connection, user_id: int, stock_id: int):
    
#    async with conn.cursor() as cur:
#        try:
#            await cur.callproc("app_get_operator_task_table", [user_id, stock_id])
#        except Exception as e:
#            print(f"ERROR callproc \"app_get_operator_task_table\": {e}")
    print(f"select_tasks {user_id}, {stock_id}")
    return

async def select_tasks(conn: Connection, user_id: int, stock_id: int) -> list:
    """ получение списка заданий """

    q = """
SELECT
    doc_id
    , material_id
    , material
    , category
    , planned_date
    , technical_process
    , operation
    , weight
    , net_weight_fact
    , exists_in_categories
    , done
FROM
    (
    SELECT * FROM task_operator_materials
    ) tom
ORDER BY
    doc_id
    , material
	, CASE
	WHEN REPLACE(category, ',', '.') REGEXP '^-?[0-9]+(\\.[0-9]+)?$' THEN
	CAST(REPLACE(category, ',', '.') AS DECIMAL(10, 3))
	ELSE 0
	END,
	category ASC
    """
    print(f"select_tasks {user_id}, {stock_id}")

    result = []
    
    async with conn.cursor() as cur:
        try:
            await cur.callproc("app_get_operator_task_table", [user_id, stock_id])
        except Exception as e:
            print(f"ERROR callproc \"app_get_operator_task_table\": {e}")
            return result    
        await cur.execute(q)
        result = await cur.fetchall()
        if isinstance(result, tuple):
            result = []
    return result

async def select_tasks_progress(conn: Connection, user_id: int, stock_id: int) -> list:

    q = """
SELECT
    material
    , doc_id
    , doc_number
    , planned_date
    , technical_process
    , operation
    , category
    , weight
    , net_weight_fact AS weight_fact
    , done
FROM
    (
    SELECT * FROM task_operator_categories
    ) toc
ORDER BY
    doc_id ASC
	, CASE
	WHEN REPLACE(category, ',', '.') REGEXP '^-?[0-9]+(\\.[0-9]+)?$' THEN
	CAST(REPLACE(category, ',', '.') AS DECIMAL(10, 3))
	ELSE 0
	END,
	category ASC
    """

    print(f"select_tasks_progress {user_id}, {stock_id}")

    result = []
    
    async with conn.cursor() as cur:
        try:
            await cur.callproc("app_get_operator_task_table", [user_id, stock_id])
        except Exception as e:
            print(f"ERROR callproc \"app_get_operator_task_table\": {e}")
            return result    
        await cur.execute(q)
        result = await cur.fetchall()
        if isinstance(result, tuple):
            result = []
    return result


async def select_task_meta(conn: Connection, stock_id: int, doc_id: int, material_id: int):

    q = """
SELECT
    ptd.id
    , ptd.doc_number
    , ptd.doc_date
    , ptd.planned_date
    , ptd.stock
    , ptd.technical_process
    , ptd.operation
    , (SELECT material FROM material WHERE id = %(material_id)s) AS material
FROM
    production_task_doc ptd
WHERE
    ptd.id = %(doc_id)s
    AND
    ptd.stock = %(stock_id)s
    AND
    ptd.done = 0
"""

    q_categories_materials = """
SELECT 
	category
	, GROUP_CONCAT(DISTINCT m.material SEPARATOR ';') AS meterials
FROM 
	selection_materials AS sm
LEFT JOIN material AS m ON
    m.id = sm.material
WHERE
    pt_doc_id = (SELECT IF(parent_doc_id = 0, id, parent_doc_id) FROM production_task_doc WHERE id = %(doc_id)s)
GROUP BY
    category
"""

    task = None
    async with conn.cursor() as cur:
        await cur.execute(q, {"doc_id": doc_id, "stock_id": stock_id, "material_id": material_id})
        task = await cur.fetchone()
        if task is not None:
            catmat = {}
            await cur.execute(q_categories_materials, {"doc_id": doc_id})
            for row in await cur.fetchall():
                catmat[row["category"]] = row["meterials"]
            task["catmat"] = catmat
    return task


async def select_processing_types(conn: Connection):
    q = """SELECT pt.id, pt.process_name FROM processing_type AS pt ORDER BY pt.id ASC"""
    processing_types: list[dict] = []
    async with conn.cursor() as cur:
        await cur.execute(q)
        processing_types.extend(await cur.fetchall())
    return processing_types


async def select_task(conn: Connection, stock_id: int, doc_id: int, material_id: int, user_id: int):
    """ получение позиций задания """
    async with conn.cursor() as cur:
        try:
            await cur.callproc("app_get_task_table", [doc_id, material_id])
        except Exception as e:
            print(f"ERROR callproc \"app_get_task_table\": {e}")
            return None    

    task = await select_task_meta(conn, stock_id, doc_id, material_id)
    if task is None:
        return task

    task["task_weights"] = await get_task_weights(conn, doc_id, material_id, user_id)
    task["processing_types"] = await select_processing_types(conn)

    q = """
SELECT 
	m.material
	,s_material AS material_id
	, s.tare_id
	, tare_mark
	, tare_type
	, tare.weight AS tara_weight
	, pti.category
	, 0 AS rest_gross_weight
	, task_tare_amount_for_document AS task_tare_amount
	, task_net_weight_for_document AS task_net_weight
	, fact_net_weight_for_document AS net_weight_fact
	, add_processing_id
	, IF(fact_net_weight_for_document > 0, 1, 0) AS done
	FROM
	(
		SELECT * FROM production_task_items
	) pti
LEFT JOIN material AS m ON m.id = pti.s_material
LEFT JOIN selection AS s ON s.id = pti.selection_id
LEFT JOIN material_data AS md ON md.key_material = pti.key_material
LEFT JOIN tare ON tare.id = md.tare_type
WHERE
    s_material = %(material_id)s
ORDER BY
    m.material
    , s.tare_id

    """

    jobs = []
    query_args = {
        "material_id": material_id
    }
    async with conn.cursor() as cur:
        await cur.execute(q, query_args)
        jobs = await cur.fetchall()
    task["jobs"] = jobs
    return task


async def get_task_weights(conn: Connection, doc_id: int, material_id: int, user_id: int):
    
    q1 = """
SELECT
	doc_id
	, material_id
	, material
	, category
	, tare_amount
	, task_weight
	, tare_amount_fact
	, net_weight_fact
	, category_details
FROM
	(
	SELECT * FROM task_weight
	) tw
"""
    task_weights: list[dict] = []

    async with conn.cursor() as cur:
        await cur.execute(q1)
        task_weights = await cur.fetchall()
        # fix: пустой результат возвращает пустой tuple, а не list
        if isinstance(task_weights, tuple):
            task_weights = []
    return task_weights


async def check_user(conn: Connection, login: str, password_hash: str):
    """ проверка авторизации пользователя """
    q = """
SELECT
    s.id
    , s.login
    , s.employee_name
    , s.can_login
FROM
    staff s
WHERE
    s.can_login IS TRUE
    AND
    s.login = %(login)s
    AND
    s.password = %(password_hash)s
    """
    result = {}
    async with conn.cursor() as cur:
        await cur.execute(q, {"login": login, "password_hash": password_hash})
        result = await cur.fetchone()
    return result


async def change_password(conn: Connection, user_id: int, password_hash: str):
    q = """
    UPDATE staff
    SET password=%(password_hash)s
    WHERE id = %(user_id)s AND can_login = 1
    """
    async with conn.cursor() as cur:
        await cur.execute(q, {"user_id": user_id, "password_hash": password_hash})


async def check_can_login(conn: Connection, user_id: int):
    """ проверка возможности входа по токену"""
    q = """ SELECT EXISTS (SELECT TRUE FROM staff s WHERE s.id = %(user_id)s AND s.can_login IS TRUE ) AS can_login """
    can_login = False
    async with conn.cursor() as cur:
        await cur.execute(q, {"user_id": user_id})
        result = await cur.fetchone()
        if result.get("can_login", 0) == 1:
            can_login = True
    return can_login


async def select_stocks(conn: Connection, user_id: int):
    q = """
SELECT
    s.id
    , s.name
    , SUM(IF(ptd.done = 0 AND pte.executor_id = %(user_id)s, 1, 0)) tasks_count
FROM
    stock s
LEFT JOIN production_task_doc ptd ON
    ptd.stock = s.id
LEFT JOIN production_task_executor pte ON
    pte.doc_id = ptd.id
WHERE
    s.app IS TRUE
GROUP BY
    s.id
    , s.name
ORDER BY
    s.name
    """
    stocks = []
    async with conn.cursor() as cur:
        await cur.execute(q, {"user_id": user_id})
        stocks = await cur.fetchall()
    return stocks


async def update_job_status(conn: Connection, doc_id: int, user_id: int, material_id: int, tara_id: int, net_weight_fact: float, add_processing_id: int, status: bool):
    #     validate_query = """
    # SELECT
    #     subq.doc_id
    #     , subq.material_id
    #     , subq.category
    #     , IFNULL(ptm.task_weight, subq.weight) - pt_done.net_weight_fact AS remaining_weight
    #     , task_job.net_weight AS job_net_weight
    #     , task_job.net_weight <= (
    #         IFNULL(ptm.task_weight, subq.weight) - pt_done.net_weight_fact
    #     ) AS can_done
    # FROM
    #     (
    #         SELECT
    #             pt.doc_id
    #             , pt.material AS material_id
    #             , pt.category
    #             , sum(pt.net_weight) AS weight
    #         FROM
    #             production_task pt
    #         WHERE
    #             pt.doc_id = %(doc_id)s
    #             AND
    #             pt.material = %(material_id)s
    #             AND pt.category = (
    #                 SELECT
    #                     category
    #                 FROM
    #                     production_task
    #                 WHERE
    #                     tare_id = %(tara_id)s
    #                     AND material = %(material_id)s
    #             )
    #         GROUP BY
    #             pt.doc_id
    #             , pt.material
    #             , pt.category
    #     ) AS subq
    # LEFT JOIN production_task_materials ptm ON
    #     ptm.doc_id = subq.doc_id
    #     AND ptm.material = subq.material_id
    #     AND ptm.category = subq.category
    # INNER JOIN (
    #         SELECT
    #             pt.doc_id
    #             , pt.material AS material_id
    #             , pt.category
    #             , sum(pt.net_weight_fact) AS net_weight_fact
    #         FROM
    #             production_task pt
    #         WHERE
    #             pt.done IS TRUE
    #         GROUP BY
    #             pt.doc_id
    #             , pt.material
    #             , pt.category
    #     ) pt_done ON
    #     pt_done.doc_id = subq.doc_id
    #     AND pt_done.material_id = subq.material_id
    #     AND pt_done.category = subq.category
    # INNER JOIN production_task AS task_job ON
    #     task_job.doc_id = subq.doc_id
    #     AND
    #     task_job.material = subq.material_id
    #     AND
    #     task_job.category = subq.category
    #     AND
    #     task_job.tare_id = %(tara_id)s
    # """
    #     # Валидация доступности действия.
    #     # Если статус работы изменяется на "выполнено", то проверяем  превышение веса по задаче в категории.
    #     # В случае превышение веса выбрасываем ошибку.
    #     can_done = True
    #     if status is True:
    #         async with conn.cursor() as cur:
    #             await cur.execute(validate_query, {"doc_id": doc_id, "material_id": material_id, "tara_id": tara_id})
    #             result = await cur.fetchone()
    #             print(result)
    #             can_done = bool(result["can_done"])
    # if can_done is False:
    #     raise Exception("Превышение веса")

#     q = """
# UPDATE
#     production_task
# SET
#     done = %(status)s
#     , net_weight_fact = CASE WHEN %(status)s IS TRUE THEN %(net_weight_fact)s ELSE 0 END
#     , tare_amount_fact = CASE WHEN %(status)s IS TRUE AND (%(net_weight_fact)s = net_weight OR net_weight = 0) THEN 1 ELSE 0 END
#     , fact_executor = CASE WHEN %(status)s IS TRUE THEN %(user_id)s ELSE 0 END
#     , add_processing_id = CASE WHEN %(status)s IS TRUE THEN %(add_processing_id)s ELSE 0 END
# WHERE
#     material = %(material_id)s
#     AND
#     doc_id = %(doc_id)s
#     AND
#     tare_id = %(tara_id)s
#     """
#     query_args = {
#          "doc_id": doc_id,
#          "user_id": user_id,
#          "material_id": material_id,
#          "tara_id": tara_id,
#          "status": status,
#          "net_weight_fact": net_weight_fact,
#          "add_processing_id": add_processing_id
#     }

#     async with conn.cursor() as cur:
#         await cur.execute(q, query_args)
#         # На всякий случай перехват ошибки, чтобы совсем не падать
#         try:
#             await cur.callproc("update_next_process_v2", [doc_id, material_id, tara_id])
#         except Exception as e:
#             print(f"ERROR callproc \"update_next_process\": {e}")
#     return

    async with conn.cursor() as cur:
        try:
            await cur.callproc("app_update_job_status", [doc_id, user_id, material_id, tara_id, net_weight_fact, add_processing_id, status])
        except Exception as e:
            print(f"ERROR callproc \"app_update_job_status\": {e}")
    return


async def update_rest_gross_weight(conn: Connection, doc_id: int, material_id: int, tare_id: int, gross_weight: float):
    q = """
UPDATE production_task
SET
    gross_weight = %(gross_weight)s
WHERE
    doc_id = %(doc_id)s
    AND
    material = %(material_id)s
    AND
    tare_id = %(tare_id)s
    """
    async with conn.cursor() as cur:
        await cur.execute(q, {
            "doc_id": doc_id,
            "material_id": material_id,
            "tare_id": tare_id,
            "gross_weight": gross_weight
        })
