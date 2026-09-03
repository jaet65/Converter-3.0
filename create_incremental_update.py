import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile


def extract_zip(zip_path, destination):
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)


def file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_map(root):
    result = {}
    for current_root, _, filenames in os.walk(root):
        for filename in filenames:
            path = os.path.join(current_root, filename)
            relative_path = os.path.relpath(path, root).replace(os.sep, "/")
            result[relative_path] = file_hash(path)
    return result


def create_incremental_update(previous_zip, current_zip, output_zip, from_version, to_version):
    with tempfile.TemporaryDirectory() as work_dir:
        previous_dir = os.path.join(work_dir, "previous")
        current_dir = os.path.join(work_dir, "current")
        patch_dir = os.path.join(work_dir, "patch")
        extract_zip(previous_zip, previous_dir)
        extract_zip(current_zip, current_dir)

        previous_root = os.path.join(previous_dir, "TrackSIM_Tools")
        current_root = os.path.join(current_dir, "TrackSIM_Tools")
        if not os.path.isdir(previous_root) or not os.path.isdir(current_root):
            raise ValueError("Los ZIP deben contener la carpeta TrackSIM_Tools")

        previous_files = file_map(previous_root)
        current_files = file_map(current_root)
        changed_files = [path for path, digest in current_files.items() if previous_files.get(path) != digest]
        deleted_files = sorted(set(previous_files) - set(current_files))

        patch_root = os.path.join(patch_dir, "TrackSIM_Tools")
        for relative_path in changed_files:
            source = os.path.join(current_root, relative_path)
            destination = os.path.join(patch_root, relative_path)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy2(source, destination)

        manifest = {
            "type": "incremental",
            "from_version": from_version,
            "to_version": to_version,
            "deleted_files": deleted_files,
        }
        with open(os.path.join(patch_dir, "update_manifest.json"), "w", encoding="utf-8") as file:
            json.dump(manifest, file, indent=2)

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for current_root, _, filenames in os.walk(patch_dir):
                for filename in filenames:
                    path = os.path.join(current_root, filename)
                    archive.write(path, os.path.relpath(path, patch_dir))

        print(f"Incremental update created: {output_zip}")
        print(f"Changed files: {len(changed_files)}")
        print(f"Deleted files: {len(deleted_files)}")


if __name__ == "__main__":
    if len(sys.argv) != 6:
        raise SystemExit("Usage: create_incremental_update.py previous.zip current.zip output.zip from_version to_version")
    create_incremental_update(*sys.argv[1:])
