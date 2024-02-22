"""
 Copyright 2024 Google LLC

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 """

from __future__ import annotations

from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY

import uuid
import logging

# https://cloud.google.com/storage/docs/retry-strategy#python.
MODIFIED_RETRY = DEFAULT_RETRY.with_deadline(300.0).with_delay(
    initial=1.0, multiplier=1.2, maximum=45.0
)

# https://cloud.google.com/storage/docs/composite-objects.
MAX_NUM_OBJECTS_TO_COMPOSE = 32

COMPOSED_PREFIX = "dataflux-composed-objects/"


def compose(
    project_name: str,
    bucket_name: str,
    destination_blob_name: str,
    objects: list[tuple[str, int]],
    storage_client: object = None,
) -> object:
    """Compose the objects into a composite object, upload the composite object to the GCS bucket and returns it.

    Args:
        project_name: the name of the GCP project.
        bucket_name: the name of the GCS bucket that holds the objects to compose.
            The function uploads the the composed object to this bucket too.
        destination_blob_name: the name of the composite object to be created.
        objects: A list of tuples which indicate the object names and sizes (in bytes) in the bucket.
            Example: [("object_name_A", 1000), ("object_name_B", 2000)]
        storage_client: the google.cloud.storage.Client initialized with the project.
            If not defined, the function will initialize the client with the project_name.

    Returns:
        the "blob" of the composed object.
    """
    if len(objects) > MAX_NUM_OBJECTS_TO_COMPOSE:
        raise ValueError(
            f"{MAX_NUM_OBJECTS_TO_COMPOSE} objects allowed to compose, received {len(objects)} objects."
        )

    if storage_client is None:
        storage_client = storage.Client(project=project_name)

    bucket = storage_client.bucket(bucket_name)
    destination = bucket.blob(destination_blob_name)

    sources = list()
    for each_object in objects:
        blob_name = each_object[0]
        sources.append(bucket.blob(blob_name))

    destination.compose(sources, retry=MODIFIED_RETRY)

    return destination


def decompose(
    project_name: str,
    bucket_name: str,
    composite_object_name: str,
    objects: list[tuple[str, int]],
    storage_client: object = None,
) -> list[bytes]:
    """Decompose the composite objects and return the decomposed objects contents in bytes.

    Args:
        project_name: the name of the GCP project.
        bucket_name: the name of the GCS bucket that holds the objects to compose.
            The function uploads the the composed object to this bucket too.
        composite_object_name: the name of the composite object to be created.
        objects: A list of tuples which indicate the object names and sizes (in bytes) in the bucket.
            Example: [("object_name_A", 1000), ("object_name_B", 2000)]
        storage_client: the google.cloud.storage.Client initialized with the project.
            If not defined, the function will initialize the client with the project_name.

    Returns:
        the contents (in bytes) of the decomposed objects.
    """
    if storage_client is None:
        storage_client = storage.Client(project=project_name)

    res = []
    composed_object_content = download_single(
        storage_client, bucket_name, composite_object_name
    )

    start = 0
    for each_object in objects:
        blob_size = each_object[1]
        content = composed_object_content[start : start + blob_size]
        res.append(content)
        start += blob_size

    if start != len(composed_object_content):
        logging.error(
            "decomposed object length = %s bytes, wanted = %s bytes.",
            start,
            len(composed_object_content),
        )
    return res


def download_single(
    storage_client: object, bucket_name: str, object_name: str
) -> bytes:
    """Download the contents of this object as a bytes object and return it.

    Args:
        storage_client: the google.cloud.storage.Client initialized with the project.
        bucket_name: the name of the GCS bucket that holds the object.
        object_name: the name of the object to download.

    Returns:
        the contents of the object in bytes.
    """
    bucket_handle = storage_client.bucket(bucket_name)
    blob = bucket_handle.blob(object_name)
    return blob.download_as_bytes(retry=MODIFIED_RETRY)


class DataFluxDownloadOptimizationParams:
    """Parameters used to optimize DataFlux download performance.

    Attributes:
        max_composite_object_size: An integer indicating a cap for the maximum size of the composite object.

    """

    def __init__(self, max_composite_object_size):
        self.max_composite_object_size = max_composite_object_size


def dataflux_download(
    project_name: str,
    bucket_name: str,
    objects: list[tuple[str, int]],
    storage_client: object = None,
    dataflux_download_optimization_params: DataFluxDownloadOptimizationParams = None,
) -> list[bytes]:
    """Perform the DataFlux download algorithm to download the object contents as bytes and return.

    Args:
        project_name: the name of the GCP project.
        bucket_name: the name of the GCS bucket that holds the objects to compose.
            The function uploads the the composed object to this bucket too.
        objects: A list of tuples which indicate the object names and sizes (in bytes) in the bucket.
            Example: [("object_name_A", 1000), ("object_name_B", 2000)]
        storage_client: the google.cloud.storage.Client initialized with the project.
            If not defined, the function will initialize the client with the project_name.
        dataflux_download_optimization_params: the paramemters used to optimize the download performance.
    Returns:
        the contents of the object in bytes.
    """
    if storage_client is None:
        storage_client = storage.Client(project=project_name)

    res = []
    max_composite_object_size = (
        dataflux_download_optimization_params.max_composite_object_size
    )

    i = 0
    while i < len(objects):
        curr_object_name = objects[i][0]
        curr_object_size = objects[i][1]

        if curr_object_size > max_composite_object_size:
            # Download the single object.
            curr_object_content = download_single(
                storage_client=storage_client,
                bucket_name=bucket_name,
                object_name=curr_object_name,
            )
            res.append(curr_object_content)
            i += 1
        else:
            # Dynamically compose and decompose based on the object size.
            objects_slice = []
            curr_size = 0

            while (
                i < len(objects)
                and curr_size <= max_composite_object_size
                and len(objects_slice) < MAX_NUM_OBJECTS_TO_COMPOSE
            ):
                curr_size += objects[i][1]
                objects_slice.append(objects[i])
                i += 1

            if len(objects_slice) == 1:
                object_name = objects_slice[0][0]
                curr_object_content = download_single(
                    storage_client=storage_client,
                    bucket_name=bucket_name,
                    object_name=object_name,
                )
                res.append(curr_object_content)
            else:
                # If the number of objects > 1, we want to compose, download, decompose and delete the composite object.
                # Need to create a unique composite name to avoid mutation on the same object among processes.
                composed_object_name = COMPOSED_PREFIX + str(uuid.uuid4())
                composed_object = compose(
                    project_name,
                    bucket_name,
                    composed_object_name,
                    objects_slice,
                    storage_client,
                )

                res.extend(
                    decompose(
                        project_name,
                        bucket_name,
                        composed_object_name,
                        objects_slice,
                        storage_client,
                    )
                )

                try:
                    composed_object.delete(retry=MODIFIED_RETRY)
                except Exception:
                    logging.exception(
                        "exception thrown when deleting the composite object."
                    )
    return res