import os
import shutil
import urllib.request
import zipfile
import json

from common import RVC_MODELS_DIR
from common import display_progress

with open(
    os.path.join(RVC_MODELS_DIR, "public_models.json"), encoding="utf8"
) as infile:
    public_models = json.load(infile)


def remove_suffix_after(text: str, occurrence: str):
    location = text.rfind(occurrence)
    if location == -1:
        return text
    else:
        return text[: location + len(occurrence)]


def copy_files_to_new_folder(file_paths, folder_path):
    os.makedirs(folder_path)
    for file_path in file_paths:
        shutil.copyfile(
            file_path, os.path.join(folder_path, os.path.basename(file_path))
        )


def extract_zip(extraction_folder, zip_name, remove_zip):
    try:
        os.makedirs(extraction_folder)
        with zipfile.ZipFile(zip_name, "r") as zip_ref:
            zip_ref.extractall(extraction_folder)

        index_filepath, model_filepath = None, None
        for root, _, files in os.walk(extraction_folder):
            for name in files:
                if (
                    name.endswith(".index")
                    and os.stat(os.path.join(root, name)).st_size > 1024 * 100
                ):
                    index_filepath = os.path.join(root, name)

                if (
                    name.endswith(".pth")
                    and os.stat(os.path.join(root, name)).st_size > 1024 * 1024 * 40
                ):
                    model_filepath = os.path.join(root, name)

        if not model_filepath:
            raise Exception(
                f"No .pth model file was found in the extracted zip folder."
            )
        # move model and index file to extraction folder

        os.rename(
            model_filepath,
            os.path.join(extraction_folder, os.path.basename(model_filepath)),
        )
        if index_filepath:
            os.rename(
                index_filepath,
                os.path.join(extraction_folder, os.path.basename(index_filepath)),
            )

        # remove any unnecessary nested folders
        for filepath in os.listdir(extraction_folder):
            if os.path.isdir(os.path.join(extraction_folder, filepath)):
                shutil.rmtree(os.path.join(extraction_folder, filepath))

    except Exception as e:
        if os.path.isdir(extraction_folder):
            shutil.rmtree(extraction_folder)
        raise e
    finally:
        if remove_zip and os.path.exists(zip_name):
            os.remove(zip_name)


def get_current_models():
    models_list = os.listdir(RVC_MODELS_DIR)
    items_to_remove = ["hubert_base.pt", "MODELS.txt", "public_models.json", "rmvpe.pt"]
    return [item for item in models_list if item not in items_to_remove]


def load_public_models_table(predicates, progress):
    models_table = []
    keys = ["name", "description", "tags", "credit", "added", "url"]
    display_progress("[~] Loading public models ...", 0.5, progress)
    for model in public_models["voice_models"]:
        if all([predicate(model) for predicate in predicates]):
            models_table.append([model[key] for key in keys])

    return models_table


def load_public_models_tags():
    return list(public_models["tags"].keys())


def load_public_models_table_w_tags(progress):
    models_table = load_public_models_table([], progress)
    tags = list(public_models["tags"].keys())
    return models_table, tags


def filter_public_models_table(tags, query, progress):

    tags_predicate = lambda model: all(tag in model["tags"] for tag in tags)
    query_predicate = (
        lambda model: query.lower()
        in f"{model['name']} {model['description']} {' '.join(model['tags'])} {model['credit']} {model['added']}".lower()
    )

    # no filter
    if len(tags) == 0 and len(query) == 0:
        filter_fns = []

    # filter based on tags and query
    elif len(tags) > 0 and len(query) > 0:
        filter_fns = [tags_predicate, query_predicate]

    # filter based on only tags
    elif len(tags) > 0:
        filter_fns = [tags_predicate]

    # filter based on only query
    else:
        filter_fns = [query_predicate]

    return load_public_models_table(filter_fns, progress)


def download_online_model(url, dir_name, progress):
    if not url:
        raise Exception("Download link to model missing!")
    if not dir_name:
        raise Exception("Model name missing!")
    extraction_folder = os.path.join(RVC_MODELS_DIR, dir_name)
    if os.path.exists(extraction_folder):
        raise Exception(
            f'Voice model directory "{dir_name}" already exists! Choose a different name for your voice model.'
        )
    zip_name = url.split("/")[-1].split("?")[0]

    if "pixeldrain.com" in url:
        url = f"https://pixeldrain.com/api/file/{zip_name}"

    display_progress(
        f"[~] Downloading voice model with name '{dir_name}'...", 0, progress
    )

    urllib.request.urlretrieve(url, zip_name)

    display_progress(f"[~] Extracting zip file...", 0.5, progress)

    extract_zip(extraction_folder, zip_name, remove_zip=True)
    return f"[+] Model with name '{dir_name}' successfully downloaded!"


def upload_local_model(input_paths, dir_name, progress):
    if not input_paths:
        raise Exception("No files selected!")
    if len(input_paths) > 2:
        raise Exception("At most two files can be uploaded!")
    if not dir_name:
        raise Exception("Model name missing!")
    output_folder = os.path.join(RVC_MODELS_DIR, dir_name)
    if os.path.exists(output_folder):
        raise Exception(
            f'Voice model directory "{dir_name}" already exists! Choose a different name for your voice model.'
        )
    input_names = [input_path.name for input_path in input_paths]
    if len(input_names) == 1:
        input_name = input_names[0]
        if input_name.endswith(".pth"):
            display_progress("[~] Copying .pth file ...", 0.5, progress)
            copy_files_to_new_folder(input_names, output_folder)
        # NOTE a .pth file is actually itself a zip file
        elif zipfile.is_zipfile(input_name):
            display_progress("[~] Extracting zip file...", 0.5, progress)
            extract_zip(output_folder, input_name, remove_zip=False)
        else:
            raise Exception(
                "Only a .pth file or a .zip file can be uploaded by itself!"
            )
    else:
        # sort two input files by extension type
        input_names_sorted = sorted(input_names, key=lambda f: os.path.splitext(f)[1])
        index_name, pth_name = input_names_sorted
        if pth_name.endswith(".pth") and index_name.endswith(".index"):
            display_progress("[~] Copying .pth file and index file ...", 0.5, progress)
            copy_files_to_new_folder(input_names, output_folder)
        else:
            raise Exception(
                "Only a .pth file and an .index file can be uploaded together!"
            )

    return f"[+] Model with name '{dir_name}' successfully uploaded!"


def delete_models(model_names, progress):
    if not model_names:
        raise Exception("No models selected!")
    display_progress("[~] Deleting selected models ...", 0.5, progress)
    for model_name in model_names:
        model_dir = os.path.join(RVC_MODELS_DIR, model_name)
        if os.path.isdir(model_dir):
            shutil.rmtree(model_dir)
    models_names_formatted = [f"'{w}'" for w in model_names]
    if len(model_names) == 1:
        return f"[+] Model with name {models_names_formatted[0]} successfully deleted!"
    else:
        first_models = ", ".join(models_names_formatted[:-1])
        last_model = models_names_formatted[-1]
        return f"[+] Models with names {first_models} and {last_model} successfully deleted!"


def delete_all_models(progress):
    all_models = get_current_models()
    display_progress("[~] Deleting all models ...", 0.5, progress)
    for model_name in all_models:
        model_dir = os.path.join(RVC_MODELS_DIR, model_name)
        if os.path.isdir(model_dir):
            shutil.rmtree(model_dir)
    return f"[+] All models successfully deleted!"
