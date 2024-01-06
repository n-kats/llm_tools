from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload


class GoogleDriveClient:
    def __init__(self, drive_service, share_folder_id: str):
        self.__drive_service = drive_service
        self.__share_folder_id = share_folder_id
        self.__cache: dict[tuple[str, str], str] = {}  # (name, parent_id) -> id

    @classmethod
    def load(cls, credentials_file: Path, share_folder_id: str):
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file
        )
        drive_service = build("drive", "v3", credentials=credentials)
        return cls(drive_service, share_folder_id)

    def mkdir(self, folder_name: str | Path) -> str:
        parent = self.__share_folder_id
        for name in Path(folder_name).parts:
            target = self.__exist_folder(name, parent)
            if target is None:
                target = self.__create_folder(name, parent)

            assert target is not None
            parent = target
        return parent

    def __exist_folder(self, name: str, parent: str) -> str | None:
        if (name, parent) in self.__cache:
            return self.__cache[(name, parent)]

        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{parent}' in parents"
        response = self.__drive_service.files().list(q=query).execute()
        return response.get("files")[0]["id"] if response.get("files") else None

    def __exist_file(self, name: str, parent: str) -> list[str]:
        query = f"name='{name}' and mimeType!='application/vnd.google-apps.folder' and trashed=false and '{parent}' in parents"
        response = self.__drive_service.files().list(q=query).execute()
        return [f["id"] for f in response.get("files", [])]

    def __create_folder(self, name: str, parent: str) -> str | None:
        subfolder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent],
        }
        subfolder = (
            self.__drive_service.files()
            .create(body=subfolder_metadata, fields="id")
            .execute()
        )
        id_ = subfolder.get("id")
        self.__cache[(name, parent)] = id_
        return id_

    def __delete_file(self, name: str, parent: str):
        file_ids = self.__exist_file(name, parent)
        for file_id in file_ids:
            self.__drive_service.files().delete(fileId=file_id).execute()

    def upload_file(
        self,
        input_file: str | Path,
        output_path: str | Path,
        mimetype: str,
        overwrite: bool = False,
    ):
        input_file = Path(input_file)
        output_path = Path(output_path)
        assert input_file.is_file()
        parent = self.mkdir(output_path.parent)
        if self.__exist_file(output_path.name, parent):
            if overwrite:
                self.__delete_file(output_path.name, parent)
            else:
                print(f"skip {output_path}")
                return
        media = MediaFileUpload(input_file, mimetype=mimetype, resumable=True)
        request = self.__drive_service.files().create(
            media_body=media, body={"name": output_path.name, "parents": [parent]}
        )
        r = None
        while r is None:
            status, r = request.next_chunk()
