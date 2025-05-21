from aiohttp.web import HTTPBadRequest, HTTPForbidden, HTTPCreated, HTTPNotFound, Request
from db import (check_user, select_task, select_tasks, change_password,
                select_stocks, update_job_status, select_tasks_progress, update_rest_gross_weight,
                check_material_item
                )
from utils import jsonify


async def login_handler(request: Request):
    """ хэндлен авторизация """
    security = request.app["crypto"]
    body = await request.json()
    login = body.get("login", "")
    password = body.get("password", "")
    password_hash = security.hash_password(password)
    user = None
    async with request.app["db"].acquire() as conn:
        user = await check_user(conn, login, password_hash)
    if user is None:
        raise HTTPForbidden()
    return await jsonify(security.create_jwt(user), request)


async def change_password_handler(request: Request):
    """ хэндер смены пароля """
    security = request.app["crypto"]
    body = await request.json()
    new_password = body.get("newPassword")
    repetition_password = body.get("repetitionPassword")
    if new_password is None or repetition_password is None or new_password != repetition_password:
        raise HTTPBadRequest(body="Проверьте корректность запроса")
    password_hash = security.hash_password(new_password)
    async with request.app["db"].acquire() as conn:
        await change_password(conn, request.user_id, password_hash)
    return HTTPCreated()


async def get_stocks(request: Request):
    """ получени списка складов """
    stocks = []
    async with request.app["db"].acquire() as conn:
        stocks = await select_stocks(conn, request.user_id)
    return await jsonify(stocks, request)


async def get_tasks(request: Request):
    """ получение списка заданий """
    stock_id = request.match_info.get("stockID", None)
    if stock_id is None:
        raise HTTPBadRequest()
    tasks = []
    async with request.app["db"].acquire() as conn:
        tasks = await select_tasks(conn, request.user_id, stock_id)
    return await jsonify(tasks, request)


async def tasks_progress(request: Request):
    """ прогресс задач """
    stock_id = request.match_info.get("stockID", None)
    if stock_id is None:
        raise HTTPBadRequest()
    tasks = []
    async with request.app["db"].acquire() as conn:
        tasks = await select_tasks_progress(conn, request.user_id, stock_id)
    return await jsonify(tasks, request)


async def get_task(request: Request):
    """ получение позиций в задании """
    # TODO: нужна привязка еще и по ID юзера
    stock_id = request.match_info.get("stockID", None)
    doc_id = request.match_info.get("taskID", None)
    material_id = request.match_info.get("materialID", None)
    if doc_id is None or stock_id is None or material_id is None:
        raise HTTPBadRequest()
    task = {}
    async with request.app["db"].acquire() as conn:
        task = await select_task(conn, int(stock_id), int(doc_id), int(material_id), request.user_id)
        if task is None:
            raise HTTPNotFound()
    return await jsonify(task, request)


async def update_job_status_handler(request: Request):
    job = await request.json()
    doc_id = job.get("taskID", None)
    material_id = job.get("materialID", None)
    tara_id = job.get("taraID", None)
    status = job.get("done", None)
    net_weight_fact = job.get("netWeightFact", None)
    rest_gross_weight = job.get("restGrossWeight", None)
    add_processing_id = job.get("processingID", 0)

    if doc_id is None or material_id is None or tara_id is None or status is None or net_weight_fact is None:
        raise HTTPBadRequest()
    async with request.app["db"].acquire() as conn:
        try:
            await update_job_status(
                conn,
                doc_id,
                request.user_id,
                material_id,
                tara_id,
                float(net_weight_fact),
                float(rest_gross_weight),
                int(add_processing_id),
                status)  # pylint: disable=too-many-function-args
        except Exception as exc:
            raise HTTPBadRequest(
                body=str(exc))  # pylint: disable=raise-missing-from
    return HTTPCreated()

async def check_material_item_handler(request: Request):
    item = await request.json()
    material_id = item.get("materialID", None)
    tara_id = item.get("taraID", None)
    doc_id = item.get("taskID", None)

    doc_list = []

    if doc_id is None or material_id is None or tara_id is None:
        raise HTTPBadRequest()
    async with request.app["db"].acquire() as conn:
        try:
            doc_list = await check_material_item(
                conn,
                material_id,
                tara_id,
                doc_id)  # pylint: disable=too-many-function-args
        except Exception as exc:
            raise HTTPBadRequest(
                body=str(exc))  # pylint: disable=raise-missing-from
        print(f"doc_list: {doc_list}")
    #return await jsonify(doc_list, request)
    return doc_list

async def update_jobs_status_handler(request: Request):
    payload: dict = await request.json()
    doc_id = payload.get("taskID", None)
    material_id = payload.get("materialID", None)
    jobs: list[dict] = payload.get("jobs", [])
    if len(jobs) == 0:
        return HTTPCreated()
    if doc_id is None or material_id is None:
        raise HTTPBadRequest()
    async with request.app["db"].acquire() as conn:
        try:
            for j in jobs:
                await update_job_status(
                    conn,
                    doc_id,
                    request.user_id,
                    material_id,
                    **j)
        except Exception as exc:
            raise HTTPBadRequest(
                body=str(exc))  # pylint: disable=raise-missing-from
    return HTTPCreated()


async def rest_gross_weight(request: Request):
    job = await request.json()
    # return HTTPCreated()
    doc_id = job.get("taskID", None)
    material_id = job.get("material_id", None)
    tare_id = job.get("tare_id", None)
    gross_weight = job.get("gross_weight", None)
    # if doc_id is None or material_id is None or tare_id is None or gross_weight is None:
    #     raise HTTPBadRequest()
    # async with request.app["db"].acquire() as conn:
    #     try:
    #         await update_rest_gross_weight(
    #             conn,
    #             doc_id,
    #             material_id,
    #             tare_id,
    #             gross_weight)
    #     except Exception as exc:
    #         raise HTTPBadRequest(
    #             body=str(exc))  # pylint: disable=raise-missing-from
    return HTTPCreated()
