from dataclasses import field

from core.services.odata_service import ODataService


class ODataMixin:

    # =====================================================
    # ALL DATA
    # =====================================================

    async def all_data(
        self,
        endpoint,
    ):
        return await ODataService.query(
            endpoint=endpoint,
        )

    # =====================================================
    # EXISTING SINGLE FILTER
    # =====================================================

    async def filter_data(
        self,
        endpoint,
        field,
        operator,
        value,
    ):

        filters = [
            {
                "field": field,
                "operator": operator,
                "value": value,
            }
        ]

        return await ODataService.query(
            endpoint=endpoint,
            filters=filters,
        )

    # =====================================================
    # MULTI FILTER
    # =====================================================

    async def filter_data_multi(
        self,
        endpoint,
        field1,
        operator1,
        value1,
        logic=None,
        field2=None,
        operator2=None,
        value2=None,
    ):

        return await ODataService.query(
            endpoint=endpoint,
            filters=[
                {
                    "field": field1,
                    "operator": operator1,
                    "value": value1,
                    "logic": logic,
                },
                {
                    "field": field2,
                    "operator": operator2,
                    "value": value2,
                } if field2 else None,
            ]
        )

    # =====================================================
    # FLEXIBLE QUERY
    # =====================================================

    async def odata(
        self,
        endpoint,
        filters=None,
        select=None,
        expand=None,
        orderby=None,
        top=None,
        skip=None,
    ):

        return await ODataService.query(
            endpoint=endpoint,
            filters=filters,
            select=select,
            expand=expand,
            orderby=orderby,
            top=top,
            skip=skip,
        )

    # =====================================================
    # FETCH SINGLE RECORD
    # =====================================================

    async def fetch_one(
        self,
        endpoint,
        field,
        value,
    ):

        return await ODataService.fetch_one(
            endpoint=endpoint,
            field=field,
            value=value,
        )

    # =====================================================
    # FETCH RELATED DATASETS
    # =====================================================

    async def fetch_related(
        self,
        queries=[],
    ):

        return await ODataService.fetch_related(
            queries=queries,
        )