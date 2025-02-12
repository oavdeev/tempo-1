# Tempo Multi-Model Introduction

![architecture](architecture.png)

In this multi-model introduction we will:

  * [Describe the project structure](#Project-Structure)
  * [Train some models](#Train-Models)
  * [Create Tempo artifacts](#Create-Tempo-Artifacts)
  * [Run unit tests](#Unit-Tests)
  * [Save python environment for our classifier](#Save-Classifier-Environment)
  * [Test Locally on Docker](#Test-Locally-on-Docker)

## Prerequisites

This notebooks needs to be run in the `tempo-examples` conda environment defined below. Create from project root folder:

```bash
conda env create --name tempo-examples --file conda/tempo-examples.yaml
```

## Project Structure


```python
!tree -P "*.py"  -I "__init__.py|__pycache__" -L 2
```

    [01;34m.[00m
    ├── [01;34martifacts[00m
    │   ├── [01;34mclassifier[00m
    │   ├── [01;34msklearn[00m
    │   └── [01;34mxgboost[00m
    ├── [01;34mk8s[00m
    │   └── [01;34mrbac[00m
    ├── [01;34msrc[00m
    │   ├── data.py
    │   ├── tempo.py
    │   └── train.py
    └── [01;34mtests[00m
        └── test_tempo.py
    
    8 directories, 4 files


## Train Models

 * This section is where as a data scientist you do your work of training models and creating artfacts.
 * For this example we train sklearn and xgboost classification models for the iris dataset.


```python
import os
from tempo.utils import logger
import logging
import numpy as np
logger.setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)
ARTIFACTS_FOLDER = os.getcwd()+"/artifacts"
```


```python
# %load src/train.py
import joblib
from sklearn.linear_model import LogisticRegression
from src.data import IrisData
from xgboost import XGBClassifier

SKLearnFolder = "sklearn"
XGBoostFolder = "xgboost"


def train_sklearn(data: IrisData, artifacts_folder: str):
    logreg = LogisticRegression(C=1e5)
    logreg.fit(data.X, data.y)
    with open(f"{artifacts_folder}/{SKLearnFolder}/model.joblib", "wb") as f:
        joblib.dump(logreg, f)


def train_xgboost(data: IrisData, artifacts_folder: str):
    clf = XGBClassifier()
    clf.fit(data.X, data.y)
    clf.save_model(f"{artifacts_folder}/{XGBoostFolder}/model.bst")

```


```python
from src.data import IrisData
from src.train import train_sklearn, train_xgboost
data = IrisData()
train_sklearn(data, ARTIFACTS_FOLDER)
train_xgboost(data, ARTIFACTS_FOLDER)
```

## Create Tempo Artifacts

 * Here we create the Tempo models and orchestration Pipeline for our final service using our models.
 * For illustration the final service will call the sklearn model and based on the result will decide to return that prediction or call the xgboost model and return that prediction instead.


```python
from src.tempo import get_tempo_artifacts
classifier, sklearn_model, xgboost_model = get_tempo_artifacts(ARTIFACTS_FOLDER)
```


```python
# %load src/tempo.py
from typing import Tuple

import numpy as np
from src.train import SKLearnFolder, XGBoostFolder

from tempo.serve.metadata import ModelFramework
from tempo.serve.model import Model
from tempo.serve.pipeline import Pipeline, PipelineModels
from tempo.serve.utils import pipeline

PipelineFolder = "classifier"
SKLearnTag = "sklearn prediction"
XGBoostTag = "xgboost prediction"


def get_tempo_artifacts(artifacts_folder: str) -> Tuple[Pipeline, Model, Model]:

    sklearn_model = Model(
        name="test-iris-sklearn",
        platform=ModelFramework.SKLearn,
        local_folder=f"{artifacts_folder}/{SKLearnFolder}",
        uri="s3://tempo/basic/sklearn",
        description="An SKLearn Iris classification model",
    )

    xgboost_model = Model(
        name="test-iris-xgboost",
        platform=ModelFramework.XGBoost,
        local_folder=f"{artifacts_folder}/{XGBoostFolder}",
        uri="s3://tempo/basic/xgboost",
        description="An XGBoost Iris classification model",
    )

    @pipeline(
        name="classifier",
        uri="s3://tempo/basic/pipeline",
        local_folder=f"{artifacts_folder}/{PipelineFolder}",
        models=PipelineModels(sklearn=sklearn_model, xgboost=xgboost_model),
        description="A pipeline to use either an sklearn or xgboost model for Iris classification",
    )
    def classifier(payload: np.ndarray) -> Tuple[np.ndarray, str]:
        res1 = classifier.models.sklearn(input=payload)

        if res1[0] == 1:
            return res1, SKLearnTag
        else:
            return classifier.models.xgboost(input=payload), XGBoostTag

    return classifier, sklearn_model, xgboost_model

```

## Unit Tests

 * Here we run our unit tests to ensure the orchestration works before running on the actual models.


```python
# %load tests/test_tempo.py
import numpy as np
from src.tempo import SKLearnTag, XGBoostTag, get_tempo_artifacts


def test_sklearn_model_used():
    classifier, _, _ = get_tempo_artifacts("")
    classifier.models.sklearn = lambda input: np.array([[1]])
    res, tag = classifier(np.array([[1, 2, 3, 4]]))
    assert res[0][0] == 1
    assert tag == SKLearnTag


def test_xgboost_model_used():
    classifier, _, _ = get_tempo_artifacts("")
    classifier.models.sklearn = lambda input: np.array([[0.2]])
    classifier.models.xgboost = lambda input: np.array([[0.1]])
    res, tag = classifier(np.array([[1, 2, 3, 4]]))
    assert res[0][0] == 0.1
    assert tag == XGBoostTag

```


```python
!python -m pytest tests/
```

    [1mTest session starts (platform: linux, Python 3.7.10, pytest 5.3.1, pytest-sugar 0.9.4)[0m
    rootdir: /home/alejandro/Programming/kubernetes/seldon/tempo, inifile: setup.cfg
    plugins: cases-3.4.6, sugar-0.9.4, xdist-1.30.0, anyio-3.2.1, requests-mock-1.7.0, django-3.8.0, forked-1.1.3, flaky-3.6.1, asyncio-0.14.0, celery-4.4.0, cov-2.8.1
    [1mcollecting ... [0m
     [36mdocs/examples/multi-model/tests/[0mtest_tempo.py[0m [32m✓[0m[32m✓[0m                [32m100% [0m[40m[32m█[0m[40m[32m████[0m[40m[32m█[0m[40m[32m████[0m
    
    Results (1.26s):
    [32m       2 passed[0m


## Save Classifier Environment

 * In preparation for running our models we save the Python environment needed for the orchestration to run as defined by a `conda.yaml` in our project.


```python
!cat artifacts/classifier/conda.yaml
```

    name: tempo
    channels:
      - defaults
    dependencies:
      - python=3.7.9
      - pip:
        - mlops-tempo @ file:///home/alejandro/Programming/kubernetes/seldon/tempo
        - mlserver==0.3.2



```python
from tempo.serve.loader import save
save(classifier)
```

    Collecting packages...
    Packing environment at '/home/alejandro/miniconda3/envs/tempo-88546d85-d920-4ba5-afbf-2bbf88afebf9' to '/home/alejandro/Programming/kubernetes/seldon/tempo/docs/examples/multi-model/artifacts/classifier/environment.tar.gz'
    [########################################] | 100% Completed | 11.5s


## Test Locally on Docker

 * Here we test our models using production images but running locally on Docker. This allows us to ensure the final production deployed model will behave as expected when deployed.


```python
from tempo import deploy_local
remote_model = deploy_local(classifier)
```


```python
remote_model.predict(np.array([[1, 2, 3, 4]]))
```




    {'output0': array([[0.00745035, 0.03121155, 0.96133804]], dtype=float32),
     'output1': 'xgboost prediction'}




```python
remote_model.undeploy()
```

## Production Option 1 (Deploy to Kubernetes with Tempo)

 * Here we illustrate how to run the final models in "production" on Kubernetes by using Tempo to deploy
 
### Prerequisites
 
Create a Kind Kubernetes cluster with Minio and Seldon Core installed using Ansible as described [here](https://tempo.readthedocs.io/en/latest/overview/quickstart.html#kubernetes-cluster-with-seldon-core).


```python
!kubectl apply -f k8s/rbac -n production
```

    secret/minio-secret configured
    serviceaccount/tempo-pipeline unchanged
    role.rbac.authorization.k8s.io/tempo-pipeline unchanged
    rolebinding.rbac.authorization.k8s.io/tempo-pipeline-rolebinding unchanged



```python
from tempo.examples.minio import create_minio_rclone
import os
create_minio_rclone(os.getcwd()+"/rclone.conf")
```


```python
from tempo.serve.loader import upload
upload(sklearn_model)
upload(xgboost_model)
upload(classifier)
```


```python
from tempo.serve.metadata import SeldonCoreOptions
runtime_options = SeldonCoreOptions(**{
        "remote_options": {
            "namespace": "production",
            "authSecretName": "minio-secret"
        }
    })
```


```python
from tempo import deploy_remote
remote_model = deploy_remote(classifier, options=runtime_options)
```


```python
print(remote_model.predict(payload=np.array([[0, 0, 0, 0]])))
print(remote_model.predict(payload=np.array([[1, 2, 3, 4]])))
```

    {'output0': array([1.], dtype=float32), 'output1': 'sklearn prediction'}
    {'output0': array([[0.00745035, 0.03121155, 0.96133804]], dtype=float32), 'output1': 'xgboost prediction'}


### Illustrate use of Deployed Model by Remote Client


```python
from tempo.seldon.k8s import SeldonKubernetesRuntime
k8s_runtime = SeldonKubernetesRuntime(runtime_options.remote_options)
models = k8s_runtime.list_models(namespace="production")
print("Name\tDescription")
for model in models:
    details = model.get_tempo().model_spec.model_details
    print(f"{details.name}\t{details.description}")
```

    Name	Description
    classifier	A pipeline to use either an sklearn or xgboost model for Iris classification
    test-iris-sklearn	An SKLearn Iris classification model
    test-iris-xgboost	An XGBoost Iris classification model



```python
models[0].predict(payload=np.array([[1, 2, 3, 4]]))
```




    {'output0': array([[0.00745035, 0.03121155, 0.96133804]], dtype=float32),
     'output1': 'xgboost prediction'}




```python
remote_model.undeploy()
```

###### Production Option 2 (Gitops)

 * We create yaml to provide to our DevOps team to deploy to a production cluster
 * We add Kustomize patches to modify the base Kubernetes yaml created by Tempo


```python
k8s_runtime = SeldonKubernetesRuntime(runtime_options.remote_options)
yaml_str = k8s_runtime.manifest(classifier)
with open(os.getcwd()+"/k8s/tempo.yaml","w") as f:
    f.write(yaml_str)
```


```python
!kustomize build k8s
```

    apiVersion: machinelearning.seldon.io/v1
    kind: SeldonDeployment
    metadata:
      annotations:
        seldon.io/tempo-description: A pipeline to use either an sklearn or xgboost model
          for Iris classification
        seldon.io/tempo-model: '{"model_details": {"name": "classifier", "local_folder":
          "/home/alejandro/Programming/kubernetes/seldon/tempo/docs/examples/multi-model/artifacts/classifier",
          "uri": "s3://tempo/basic/pipeline", "platform": "tempo", "inputs": {"args":
          [{"ty": "numpy.ndarray", "name": "payload"}]}, "outputs": {"args": [{"ty": "numpy.ndarray",
          "name": null}, {"ty": "builtins.str", "name": null}]}, "description": "A pipeline
          to use either an sklearn or xgboost model for Iris classification"}, "protocol":
          "tempo.kfserving.protocol.KFServingV2Protocol", "runtime_options": {"runtime":
          "tempo.seldon.SeldonKubernetesRuntime", "state_options": {"state_type": "LOCAL",
          "key_prefix": "", "host": "", "port": ""}, "insights_options": {"worker_endpoint":
          "", "batch_size": 1, "parallelism": 1, "retries": 3, "window_time": 0, "mode_type":
          "NONE", "in_asyncio": false}, "ingress_options": {"ingress": "tempo.ingress.istio.IstioIngress",
          "ssl": false, "verify_ssl": true}, "replicas": 1, "minReplicas": null, "maxReplicas":
          null, "authSecretName": "minio-secret", "serviceAccountName": null, "add_svc_orchestrator":
          false, "namespace": "production"}}'
      labels:
        seldon.io/tempo: "true"
      name: classifier
      namespace: production
    spec:
      predictors:
      - annotations:
          seldon.io/no-engine: "true"
        componentSpecs:
        - spec:
            containers:
            - name: classifier
              resources:
                limits:
                  cpu: 1
                  memory: 1Gi
                requests:
                  cpu: 500m
                  memory: 500Mi
        graph:
          envSecretRefName: minio-secret
          implementation: TEMPO_SERVER
          modelUri: s3://tempo/basic/pipeline
          name: classifier
          serviceAccountName: tempo-pipeline
          type: MODEL
        name: default
        replicas: 1
      protocol: kfserving
    ---
    apiVersion: machinelearning.seldon.io/v1
    kind: SeldonDeployment
    metadata:
      annotations:
        seldon.io/tempo-description: An SKLearn Iris classification model
        seldon.io/tempo-model: '{"model_details": {"name": "test-iris-sklearn", "local_folder":
          "/home/alejandro/Programming/kubernetes/seldon/tempo/docs/examples/multi-model/artifacts/sklearn",
          "uri": "s3://tempo/basic/sklearn", "platform": "sklearn", "inputs": {"args":
          [{"ty": "numpy.ndarray", "name": null}]}, "outputs": {"args": [{"ty": "numpy.ndarray",
          "name": null}]}, "description": "An SKLearn Iris classification model"}, "protocol":
          "tempo.kfserving.protocol.KFServingV2Protocol", "runtime_options": {"runtime":
          "tempo.seldon.SeldonKubernetesRuntime", "state_options": {"state_type": "LOCAL",
          "key_prefix": "", "host": "", "port": ""}, "insights_options": {"worker_endpoint":
          "", "batch_size": 1, "parallelism": 1, "retries": 3, "window_time": 0, "mode_type":
          "NONE", "in_asyncio": false}, "ingress_options": {"ingress": "tempo.ingress.istio.IstioIngress",
          "ssl": false, "verify_ssl": true}, "replicas": 1, "minReplicas": null, "maxReplicas":
          null, "authSecretName": "minio-secret", "serviceAccountName": null, "add_svc_orchestrator":
          false, "namespace": "production"}}'
      labels:
        seldon.io/tempo: "true"
      name: test-iris-sklearn
      namespace: production
    spec:
      predictors:
      - annotations:
          seldon.io/no-engine: "true"
        graph:
          envSecretRefName: minio-secret
          implementation: SKLEARN_SERVER
          modelUri: s3://tempo/basic/sklearn
          name: test-iris-sklearn
          type: MODEL
        name: default
        replicas: 1
      protocol: kfserving
    ---
    apiVersion: machinelearning.seldon.io/v1
    kind: SeldonDeployment
    metadata:
      annotations:
        seldon.io/tempo-description: An XGBoost Iris classification model
        seldon.io/tempo-model: '{"model_details": {"name": "test-iris-xgboost", "local_folder":
          "/home/alejandro/Programming/kubernetes/seldon/tempo/docs/examples/multi-model/artifacts/xgboost",
          "uri": "s3://tempo/basic/xgboost", "platform": "xgboost", "inputs": {"args":
          [{"ty": "numpy.ndarray", "name": null}]}, "outputs": {"args": [{"ty": "numpy.ndarray",
          "name": null}]}, "description": "An XGBoost Iris classification model"}, "protocol":
          "tempo.kfserving.protocol.KFServingV2Protocol", "runtime_options": {"runtime":
          "tempo.seldon.SeldonKubernetesRuntime", "state_options": {"state_type": "LOCAL",
          "key_prefix": "", "host": "", "port": ""}, "insights_options": {"worker_endpoint":
          "", "batch_size": 1, "parallelism": 1, "retries": 3, "window_time": 0, "mode_type":
          "NONE", "in_asyncio": false}, "ingress_options": {"ingress": "tempo.ingress.istio.IstioIngress",
          "ssl": false, "verify_ssl": true}, "replicas": 1, "minReplicas": null, "maxReplicas":
          null, "authSecretName": "minio-secret", "serviceAccountName": null, "add_svc_orchestrator":
          false, "namespace": "production"}}'
      labels:
        seldon.io/tempo: "true"
      name: test-iris-xgboost
      namespace: production
    spec:
      predictors:
      - annotations:
          seldon.io/no-engine: "true"
        graph:
          envSecretRefName: minio-secret
          implementation: XGBOOST_SERVER
          modelUri: s3://tempo/basic/xgboost
          name: test-iris-xgboost
          type: MODEL
        name: default
        replicas: 1
      protocol: kfserving



```python

```
