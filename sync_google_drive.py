import argparse
from pathlib import Path
from utils.gcp_utils import GoogleDriveClient


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--target_dir", type=Path, required=True)
    parser.add_argument("--folder_id", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    client = GoogleDriveClient.load(args.credentials, args.folder_id)
    for ext, mimetype in [(".wav", "audio/wav"), (".txt", "text/plain"), (".mp3", "audio/mp3")]:
        for path in args.target_dir.glob(f"**/*{ext}"):
            print(path)
            client.upload_file(
                path, path.relative_to(
                    args.target_dir), mimetype, args.overwrite)


if __name__ == '__main__':
    main()
