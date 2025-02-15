#!/usr/bin/env python3
#coding=utf-8

import time
import sys
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import statsmodels.api as sm
from statsmodels.tools import eval_measures
import statsmodels.formula.api as smf

start_time = time.time()

train_feature_path = './train_feature.csv'
train_label_path = './train_label.csv'
test_feature_path = './test_feature.csv'
submission_path = './submission_format.csv'
prediction_path = './prediction.csv'

### Read data
def preprocess_data(data_path, labels_path=None):
    # load data and set index to city, year, weekofyear
    df = pd.read_csv(data_path, index_col=[0, 1, 2])
    
    # select features we want
    features = ['reanalysis_specific_humidity_g_per_kg', 
                 'reanalysis_dew_point_temp_k', 
                 'station_avg_temp_c', 
                 'station_min_temp_c']
    df = df[features]
    
    # fill missing values
    df.fillna(method='ffill', inplace=True)

    # add labels to dataframe
    if labels_path:
        labels = pd.read_csv(labels_path, index_col=[0, 1, 2])
        df = df.join(labels)
    
    # separate san juan and iquitos
    sj = df.loc['sj']
    iq = df.loc['iq']
    
    return sj, iq

### Train model
def get_best_model(train, test):
    # Step 1: specify the form of the model
    model_formula = "total_cases ~ 1 + " \
                    "reanalysis_specific_humidity_g_per_kg + " \
                    "reanalysis_dew_point_temp_k + " \
                    "station_min_temp_c + " \
                    "station_avg_temp_c"
    
    grid = np.append(10 ** np.arange(-8, -3, dtype=np.float64), \
    						5 * 10 ** np.arange(-8, -3, dtype=np.float64))
                    
    best_alpha = []
    best_score = 1000
        
    # Step 2: Find the best hyper parameter, alpha
    for alpha in grid:
        model = smf.glm(formula=model_formula,
                        data=train,
                        family=sm.families.NegativeBinomial(alpha=alpha))

        results = model.fit()
        predictions = results.predict(test).astype(int)
        score = eval_measures.meanabs(predictions, test.total_cases)

        if score < best_score:
            best_alpha = alpha
            best_score = score

    print('best alpha = ', best_alpha)
    print('best score = ', best_score)
            
    # Step 3: refit on entire dataset
    full_dataset = pd.concat([train, test])
    model = smf.glm(formula=model_formula,
                    data=full_dataset,
                    family=sm.families.NegativeBinomial(alpha=best_alpha))

    fitted_model = model.fit()
    return (fitted_model, best_alpha, best_score)

### Read training data
sj_train, iq_train = preprocess_data(train_feature_path, labels_path=train_label_path)

### Split validation
sj_train_subtrain = sj_train.head(800)
sj_train_subtest = sj_train.tail(sj_train.shape[0] - 800)

iq_train_subtrain = iq_train.head(400)
iq_train_subtest = iq_train.tail(iq_train.shape[0] - 400)

### Training
(sj_best_model, sj_best_alpha, sj_best_score) = get_best_model(sj_train_subtrain, sj_train_subtest)
(iq_best_model, iq_best_alpha, iq_best_score) = get_best_model(iq_train_subtrain, iq_train_subtest)

print('average mae = ', (936*sj_best_score + 520*iq_best_score) / 1456)

### Testing
sj_test, iq_test = preprocess_data(test_feature_path)

sj_predictions = sj_best_model.predict(sj_test).astype(int)
iq_predictions = iq_best_model.predict(iq_test).astype(int)

submission = pd.read_csv(submission_path, index_col=[0, 1, 2])

submission.total_cases = np.concatenate([sj_predictions, iq_predictions])
submission.to_csv(prediction_path)

print('Elapse time:', time.time()-start_time, 'seconds\n')

