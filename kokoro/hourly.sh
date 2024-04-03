# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#!/bin/bash

# Fail on any error.
set -e

# Code under repo is checked out to this directory.
cd "${KOKORO_ARTIFACTS_DIR}/github/dataflux-client-python"

function install_requirements() {
    echo Installing requirements.

    echo Installing python3-pip.
    sudo apt-get -y install python3-pip

    echo Installing required dependencies.
    pip install -r requirements.txt
    
    echo Installing dataflux core.
    pip install .
}

function run_hourly_tests() {
    echo Running performance tests.
    python3 dataflux_core/performance_tests/list_only.py --project=$PROJECT --bucket=$BUCKET --bucket-file-count=500000 --num-workers=32 --prefix=$PREFIX
}

install_requirements
run_hourly_tests