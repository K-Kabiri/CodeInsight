from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Shared pagination for owner-scoped list endpoints (projects,
    versions, analyses). The public metric catalog stays unpaginated:
    it is a fixed 12-item list the frontend needs in full.
    """

    page_size = 20
