import asyncio
import aiohttp

from django.conf import settings


class ODataService:

    auth = aiohttp.BasicAuth(
        settings.WEB_SERVICE_UID,
        settings.WEB_SERVICE_PWD,
    )

    # =====================================================
    # CORE QUERY
    # =====================================================

    @classmethod
    async def query(
        cls,
        endpoint,
        filters=None,
        select=None,
        expand=None,
        orderby=None,
        top=None,
        skip=None,
    ):

        params = []

        # =====================================================
        # FILTERS
        # =====================================================

        if filters:

            filter_query = []

            for i, item in enumerate(filters):

                if not item:
                    continue

                field = item.get("field")
                operator = item.get("operator", "eq")
                value = item.get("value")
                logic = item.get("logic")

                # =================================================
                # HANDLE BOOLEAN / NULL / STRING VALUES
                # =================================================

                if isinstance(value, bool):
                    value = str(value).lower()
                    clause = f"{field} {operator} {value}"

                elif value is None:
                    clause = f"{field} {operator} null"

                else:
                    clause = f"{field} {operator} '{value}'"

                # =================================================
                # APPEND LOGIC
                # =================================================

                if i > 0 and logic:
                    clause = f"{logic} {clause}"

                filter_query.append(clause)

            if filter_query:
                params.append(
                    "$filter=" + " ".join(filter_query)
                )

        # =====================================================
        # SELECT
        # =====================================================

        if select:

            params.append(
                "$select=" + ",".join(select)
            )

        # =====================================================
        # EXPAND
        # =====================================================

        if expand:

            params.append(
                "$expand=" + ",".join(expand)
            )

        # =====================================================
        # ORDER BY
        # =====================================================

        if orderby:

            params.append(
                f"$orderby={orderby}"
            )

        # =====================================================
        # PAGINATION
        # =====================================================

        if top:

            params.append(
                f"$top={top}"
            )

        if skip:

            params.append(
                f"$skip={skip}"
            )

        # =====================================================
        # FINAL URL
        # =====================================================

        query_string = "&".join(params)

        url = settings.O_DATA.format(
            f"{endpoint}?{query_string}"
        )

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                auth=cls.auth,
            ) as response:

                data = await response.json()

                return data.get("value", [])

    # =====================================================
    # SINGLE RECORD
    # =====================================================

    @classmethod
    async def fetch_one(
        cls,
        endpoint,
        property,
        value,
    ):

        response = await cls.query(
            endpoint=endpoint,
            filters=[
                {
                    "field": property,
                    "operator": "eq",
                    "value": value,
                }
            ],
            top=1,
        )

        if response:
            return response[0]

        return None

    # =====================================================
    # CONCURRENT MULTI QUERY
    # =====================================================

    @classmethod
    async def fetch_related(
        cls,
        queries=[],
    ):
        """
        queries = [
            {
                "endpoint": "/QyApprovalEntries",
                "filters": [...],
                "alias": "Approvers"
            }
        ]
        """

        tasks = []

        for query in queries:

            task = asyncio.create_task(
                cls.query(
                    endpoint=query.get("endpoint"),
                    filters=query.get("filters"),
                    select=query.get("select"),
                    expand=query.get("expand"),
                    orderby=query.get("orderby"),
                    top=query.get("top"),
                    skip=query.get("skip"),
                )
            )

            tasks.append(
                (
                    query.get("alias"),
                    task,
                )
            )

        responses = await asyncio.gather(
            *[task[1] for task in tasks]
        )

        return {
            tasks[index][0]: responses[index]
            for index in range(len(tasks))
        }