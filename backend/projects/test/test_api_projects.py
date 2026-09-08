import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from projects.models import Project, ProjectVersion


class ProjectsApiTestCase(APITestCase):
    """
    Shared fixtures: two users with token clients and a throwaway
    MEDIA_ROOT so uploaded versions never touch the real media dir.
    """

    def setUp(self):
        self._media_root = tempfile.mkdtemp(
            prefix="codeinsight-test-media-"
        )
        self._media_override = override_settings(
            MEDIA_ROOT=self._media_root
        )
        self._media_override.enable()

        self.alice = User.objects.create_user(
            username="alice",
            password="pass-alice",
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="pass-bob",
        )
        self.alice_client = self._client_for(self.alice)
        self.bob_client = self._client_for(self.bob)

    def tearDown(self):
        self._media_override.disable()
        shutil.rmtree(
            self._media_root,
            ignore_errors=True,
        )

    def _client_for(self, user):
        token = Token.objects.create(user=user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        return client

    def _create_project(self, client, name="My Project"):
        response = client.post(
            "/api/projects/",
            {"name": name, "description": "test"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return Project.objects.get(id=response.data["id"])

    def _upload(self, client, project, file):
        return client.post(
            f"/api/projects/{project.id}/versions/",
            {"source_file": file},
            format="multipart",
        )


class ProjectCrudTest(ProjectsApiTestCase):

    def test_create_project_assigns_owner_from_request(self):
        response = self.alice_client.post(
            "/api/projects/",
            {"name": "My Project", "description": "desc"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "My Project")
        self.assertEqual(response.data["description"], "desc")
        project = Project.objects.get(id=response.data["id"])
        self.assertEqual(project.owner, self.alice)

    def test_create_project_requires_authentication(self):
        response = self.client.post(
            "/api/projects/",
            {"name": "My Project"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_list_projects_returns_only_own_projects(self):
        alice_project = self._create_project(
            self.alice_client,
            name="Alice's",
        )
        self._create_project(
            self.bob_client,
            name="Bob's",
        )

        response = self.alice_client.get("/api/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            alice_project.id,
        )
        self.assertEqual(
            response.data["results"][0]["name"],
            "Alice's",
        )

        response = self.bob_client.get("/api/projects/")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Bob's",
        )

    def test_retrieve_own_project(self):
        project = self._create_project(self.alice_client)
        response = self.alice_client.get(
            f"/api/projects/{project.id}/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], project.id)

    def test_retrieve_other_users_project_returns_404(self):
        project = self._create_project(self.alice_client)
        response = self.bob_client.get(
            f"/api/projects/{project.id}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_list_projects_requires_authentication(self):
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, 401)

    def test_retrieve_requires_authentication(self):
        project = self._create_project(self.alice_client)
        response = self.client.get(
            f"/api/projects/{project.id}/"
        )
        self.assertEqual(response.status_code, 401)

    def test_update_own_project(self):
        project = self._create_project(self.alice_client)
        response = self.alice_client.patch(
            f"/api/projects/{project.id}/",
            {"name": "Renamed"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Renamed")

    def test_update_other_users_project_returns_404(self):
        project = self._create_project(self.alice_client)
        response = self.bob_client.patch(
            f"/api/projects/{project.id}/",
            {"name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_other_users_project_returns_404(self):
        project = self._create_project(self.alice_client)
        response = self.bob_client.delete(
            f"/api/projects/{project.id}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_create_project_without_name_returns_400(self):
        response = self.alice_client.post(
            "/api/projects/",
            {"description": "missing the name"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_own_project_removes_versions(self):
        project = self._create_project(self.alice_client)
        response = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("main.py", b"print('hi')\n"),
        )
        self.assertEqual(response.status_code, 201)

        response = self.alice_client.delete(
            f"/api/projects/{project.id}/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Project.objects.filter(id=project.id).exists()
        )
        self.assertFalse(
            ProjectVersion.objects.filter(
                project_id=project.id
            ).exists()
        )


class VersionUploadTest(ProjectsApiTestCase):

    def test_upload_py_file_creates_version_one(self):
        project = self._create_project(self.alice_client)
        response = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("hello.py", b"print('hi')\n"),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["version_number"], 1)
        self.assertIn("source_file", response.data)
        self.assertEqual(
            ProjectVersion.objects.filter(
                project=project
            ).count(),
            1,
        )

    def test_upload_zip_archive_creates_version(self):
        project = self._create_project(self.alice_client)
        response = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile(
                "bundle.zip",
                b"not really a zip",
                content_type="application/zip",
            ),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["version_number"], 1)

    def test_subsequent_uploads_increment_version_number(self):
        project = self._create_project(self.alice_client)
        first = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("v1.py", b"print(1)\n"),
        )
        second = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("v2.py", b"print(2)\n"),
        )
        self.assertEqual(first.data["version_number"], 1)
        self.assertEqual(second.data["version_number"], 2)

    def test_unsupported_suffix_returns_400_with_message(self):
        project = self._create_project(self.alice_client)
        response = self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("notes.txt", b"hello"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("source_file", response.data)
        message = str(response.data["source_file"][0])
        self.assertIn("txt", message)
        self.assertEqual(
            ProjectVersion.objects.filter(
                project=project
            ).count(),
            0,
        )

    def test_upload_requires_authentication(self):
        project = self._create_project(self.alice_client)
        response = self.client.post(
            f"/api/projects/{project.id}/versions/",
            {"source_file": SimpleUploadedFile("x.py", b"x")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 401)

    def test_upload_to_other_users_project_returns_404(self):
        project = self._create_project(self.alice_client)
        response = self._upload(
            self.bob_client,
            project,
            SimpleUploadedFile("sneaky.py", b"x"),
        )
        self.assertEqual(response.status_code, 404)


class VersionListTest(ProjectsApiTestCase):

    def test_list_versions_returns_uploaded_versions(self):
        project = self._create_project(self.alice_client)
        self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("v1.py", b"print(1)\n"),
        )
        self._upload(
            self.alice_client,
            project,
            SimpleUploadedFile("v2.py", b"print(2)\n"),
        )

        response = self.alice_client.get(
            f"/api/projects/{project.id}/versions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(
            {
                item["version_number"]
                for item in response.data["results"]
            },
            {1, 2},
        )

    def test_list_versions_is_empty_for_new_project(self):
        project = self._create_project(self.alice_client)
        response = self.alice_client.get(
            f"/api/projects/{project.id}/versions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_list_other_users_versions_returns_404(self):
        project = self._create_project(self.alice_client)
        response = self.bob_client.get(
            f"/api/projects/{project.id}/versions/"
        )
        self.assertEqual(response.status_code, 404)

    def test_list_versions_requires_authentication(self):
        project = self._create_project(self.alice_client)
        response = self.client.get(
            f"/api/projects/{project.id}/versions/"
        )
        self.assertEqual(response.status_code, 401)


class ProjectPaginationTest(ProjectsApiTestCase):

    def test_projects_list_is_paginated(self):
        for index in range(25):
            Project.objects.create(
                owner=self.alice,
                name=f"Project {index}",
            )

        response = self.alice_client.get("/api/projects/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

        response = self.alice_client.get("/api/projects/?page=2")
        self.assertEqual(len(response.data["results"]), 5)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])


class VersionPaginationTest(ProjectsApiTestCase):

    def test_versions_list_is_paginated(self):
        project = self._create_project(self.alice_client)

        for index in range(25):
            ProjectVersion.objects.create(
                project=project,
                version_number=index + 1,
                source_file=SimpleUploadedFile(
                    f"file{index}.py",
                    b"x = 1\n",
                ),
            )

        response = self.alice_client.get(
            f"/api/projects/{project.id}/versions/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(response.data["results"]), 20)

        response = self.alice_client.get(
            f"/api/projects/{project.id}/versions/?page=2"
        )
        self.assertEqual(len(response.data["results"]), 5)
