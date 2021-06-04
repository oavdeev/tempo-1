import joblib
import os

from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from src.data import IrisData
from src.constants import SKLearnFolder, XGBoostFolder


def train_sklearn(data: IrisData):
    logreg = LogisticRegression(C=1e5)
    logreg.fit(data.X, data.y)

    model_path = os.path.join(SKLearnFolder, "model.joblib")
    with open(model_path, "wb") as f:
        joblib.dump(logreg, f)


def train_xgboost(data: IrisData):
    clf = XGBClassifier()
    clf.fit(data.X, data.y)

    model_path = os.path.join(XGBoostFolder, "model.json")
    clf.save_model(model_path)
