import argparse
from pathlib import Path
from utils.gcp_utils import GoogleDriveClient
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--target_dir", type=Path, required=True)
    parser.add_argument("--folder_id", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    client = GoogleDriveClient.load(args.credentials, args.folder_id)
    for path in args.target_dir.glob("**/*.wav"):
        print(path)
        client.upload_file(path, path.relative_to(args.target_dir), "audio/wav")

if __name__ == '__main__':
    main()
