#!/usr/bin/env python3
#coding=utf-8

import numpy as np
import pandas as pd
import sys
import time
import h5py
from keras.models import load_model

# limit gpu resource usage
# import tensorflow as tf
# from keras.backend.tensorflow_backend import set_session
# config = tf.ConfigProto()
# config.gpu_options.per_process_gpu_memory_fraction = 0.3
# set_session(tf.Session(config=config))

start_time = time.time()

train_feature_path = './data/train_feature.csv'
train_label_path = './data/train_label.csv'
test_feature_path = './data/test_feature.csv'
prediction_path = './rnn2221.csv'
arg = False

g_train_feature = []
g_train_label = []
g_test_feature = []

def reshape(train_feature,weekConcat,weekPredAfter):
    print('Reshape.')
    trainRow = train_feature.shape[0]-(weekConcat-1) -(weekPredAfter)
    col = train_feature.shape[1]
    trainF = np.zeros((trainRow, weekConcat, col)) 
    for i in range(0,trainRow):
        trainF[i] =  train_feature[i:i+weekConcat,:]  
    return trainF

def drawPeak():
    ## peak label
    peak = np.hstack((np.arange(15,38),np.arange(67,90)))
    peak = np.hstack((peak,np.arange(120,143)))
    peak = np.hstack((peak,np.arange(172,195)))
    peak = np.hstack((peak,np.arange(224,245)))
    peak = peak - 2
    return peak

def main(model_sj_path, model_iq_path, add, weekConcat, weekPredAfter):   
    #-----Read training data---------------------------------------------------------
    print('Reading data from:', train_feature_path)
    train_feature = pd.read_csv(train_feature_path, encoding='big5')
    if weekPredAfter == 2:
        train_feature.fillna(method='ffill', inplace=True)
        train_feature = train_feature.values
        train_feature = train_feature.astype(str)
    else:
        #train_feature.fillna(method='ffill', inplace=True)
        train_feature = train_feature.values
        train_feature = train_feature.astype(str)
        train_feature[train_feature == 'nan'] = '0.0'
    train_feature = np.hstack((train_feature[:,2].reshape(len(train_feature),1), train_feature[:,4::]))
    train_feature = train_feature.astype(float)

    #-----Read training label--------------------------------------------------------
    print('Reading data from:', train_label_path)
    train_label = pd.read_csv(train_label_path, encoding='big5')
    train_label = train_label.values
    train_label = train_label[:,3].reshape(len(train_label),1).astype(float)
    
    #-----Read testing data---------------------------------------------------------
    print('Reading data from:', test_feature_path)
    test_feature = pd.read_csv(test_feature_path, encoding='big5')
    if weekPredAfter == 2:
        test_feature.fillna(method='ffill', inplace=True)
        test_feature = test_feature.values
        test_feature = test_feature.astype(str)
    else:
        test_feature = test_feature.values
        test_feature = test_feature.astype(str)
        test_feature[test_feature == 'nan'] = '0.0'
    test_feature = np.hstack((test_feature[:,2].reshape(len(test_feature),1), test_feature[:,4::]))
    test_feature = test_feature.astype(float)

    weekPredAfter = 1
    
    if add == 1:
        train_feature = np.hstack((train_feature, np.power(train_feature[:,[8,10,14,16,19]],3)))
        test_feature = np.hstack((test_feature,np.power(test_feature[:,[8,10,14,16,19]],3)))
    elif add == 2:
        train_feature = np.hstack((train_feature, np.square(train_feature)))
        test_feature = np.hstack((test_feature, np.square(test_feature)))
    elif add == 3:
        train_feature = train_feature[:,[8,14,16,19]]
        test_feature = test_feature[:,[8,14,16,19]]
    elif add == 4:
        train_feature = np.hstack((train_feature[:,[8,14,16,19]], np.square(train_feature[:,[8,14,16,19]])))
        test_feature = np.hstack((test_feature[:,[8,14,16,19]], np.square(test_feature[:,[8,14,16,19]])))
    elif add == 5:
        train_feature[:,0] = np.abs(np.cos((train_feature[:,0]-1)/52 * np.pi))
        test_feature[:,0] = np.abs(np.cos((test_feature[:,0]-1)/52 * np.pi))
        train_feature = train_feature[:,[0,8,14,16,19]]
        test_feature = test_feature[:,[0,8,14,16,19]]
    elif add == 6:
        train_feature[:,0] = np.abs(np.cos((train_feature[:,0]-1)/52 * np.pi))
        test_feature[:,0] = np.abs(np.cos((test_feature[:,0]-1)/52 * np.pi))
        train_feature = np.hstack((train_feature[:,[0,8,14,16,19]], np.square(train_feature[:,[8,14,16,19]])))
        test_feature = np.hstack((test_feature[:,[0,8,14,16,19]], np.square(test_feature[:,[8,14,16,19]])))
        
    ## Seperate diff city
    train_sj_f = train_feature[:936]
    train_sj_l = train_label[:936]
    train_iq_f = train_feature[936::]
    train_iq_l = train_label[936::]
    
    test_sj = test_feature[:260]
    test_iq = test_feature[260::]
    test_sj_fakeLabel = np.zeros((test_sj.shape[0],1))
    test_iq_fakeLabel = np.zeros((test_iq.shape[0],1))
    
    ## integrate train & test + count mean & std    
    all_feature_sj = np.vstack((train_sj_f, test_sj))    
    all_feature_iq = np.vstack((train_iq_f, test_iq))
    mean_sj = np.mean(all_feature_sj, axis=0)
    std_sj = np.std(all_feature_sj, axis=0)
    mean_iq = np.mean(all_feature_iq, axis=0)
    std_iq = np.std(all_feature_iq, axis=0)
    mean_sj = np.append(mean_sj,(np.mean(train_sj_l)))    
    std_sj = np.append(std_sj,(np.std(train_sj_l)))
    mean_iq = np.append(mean_iq,(np.mean(train_iq_l)))    
    std_iq = np.append(std_iq,(np.std(train_iq_l)))    
    
    ## integrate label & fakeLabel
    test_sj = np.vstack((train_sj_f[train_sj_f.shape[0]-((weekConcat-1)+weekPredAfter):],test_sj))
    test_iq = np.vstack((train_iq_f[train_iq_f.shape[0]-((weekConcat-1)+weekPredAfter):],test_iq))
    test_sj_fakeLabel = np.vstack((train_sj_l[train_sj_l.shape[0]-((weekConcat-1)+weekPredAfter):],test_sj_fakeLabel))
    test_iq_fakeLabel = np.vstack((train_iq_l[train_iq_l.shape[0]-((weekConcat-1)+weekPredAfter):],test_iq_fakeLabel))
    test_sj = np.hstack((test_sj,test_sj_fakeLabel))
    test_iq = np.hstack((test_iq,test_iq_fakeLabel))
    
    ## reshape
    test_sj = reshape(test_sj,weekConcat,weekPredAfter)
    test_iq = reshape(test_iq,weekConcat,weekPredAfter)
        
    ## normalization
    test_sj = (test_sj - mean_sj) / std_sj
    test_iq = (test_iq - mean_iq) / std_iq
     
    ## pred
    y_pred_sj = np.zeros((test_sj.shape[0]))
    y_pred_iq = np.zeros((test_iq.shape[0]))
    model_sj = load_model(model_sj_path)
    print('Load sj model:', model_sj_path)
    model_iq = load_model(model_iq_path)
    print('Load iq model:', model_iq_path)
    rowsj = test_sj.shape[0]
    rowiq = test_iq.shape[0]
    for i in range(0,rowsj):
        y_pred_sj[i] = model_sj.predict(np.reshape(test_sj[i],(1,test_sj.shape[1],test_sj.shape[2])))[0][0]

        normPred = (y_pred_sj[i] - mean_sj[mean_sj.shape[0]-1])/std_sj[std_sj.shape[0]-1]
        for j in range(weekPredAfter, weekConcat+weekPredAfter):
            if (j+i) < test_sj.shape[0]:
                test_sj[j+i,(weekConcat-j),(std_sj.shape[0]-1)] = normPred
                
    for i in range(0,rowiq):
        y_pred_iq[i] = model_iq.predict(np.reshape(test_iq[i],(1,test_iq.shape[1],test_iq.shape[2])))[0][0]
        normPred = (y_pred_iq[i] - mean_iq[mean_iq.shape[0]-1])/std_iq[std_iq.shape[0]-1]
        for j in range(weekPredAfter, weekConcat+weekPredAfter):
            if (j+i) < test_iq.shape[0]:
                test_iq[j+i,(weekConcat-j),(std_iq.shape[0]-1)] = normPred
        
    y_pred = np.vstack((np.reshape(y_pred_sj,(y_pred_sj.shape[0],1)), np.reshape(y_pred_iq,(y_pred_iq.shape[0],1))))
    return y_pred
    
if __name__=='__main__':    
    test_feature = pd.read_csv(test_feature_path, encoding='big5')
    test_feature = test_feature.values
    test_feature = test_feature.astype(str)
    test_tags = np.asarray(test_feature[:,:3])
    
    weekConcat_1 = 10
    model_sj_path_1 = './rnn/labelsj32_3000_100_adam_elu_softmax_1sj_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.53_256_0.4_1280.4_64_0.4_10_3_.h5py'
    model_iq_path_1 = './rnn/labeliq32_3000_100_adam_elu_softmax_1iq_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.51_256_0.4_1280.4_64_0.4_10_3_.h5py'
    add_1 = 3
    weekPredAfter_1 = 1

    weekConcat_2 = 10 
    model_sj_path_2 = './rnn/labelsj32_3000_100_adam_elu_softmax_2sj_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.53_256_0.4_1280.4_64_0.4_10_4_.h5py'
    model_iq_path_2 = './rnn/labeliq32_3000_100_adam_elu_softmax_2iq_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.52_256_0.4_1280.4_64_0.4_10_4_.h5py'
    add_2 = 4
    weekPredAfter_2 = 1

    weekConcat_3 = 10
    model_sj_path_3 = './rnn/labelsj32_3000_100_adam_elu_softmax_1sj_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.51_256_0.4_1280.4_64_0.4_10_3_.h5py'
    model_iq_path_3 = './rnn/labeliq32_3000_100_adam_elu_softmax_2iq_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.53_256_0.4_1280.4_64_0.4_10_3_.h5py'
    add_3 = 3
    weekPredAfter_3 = 1

    weekConcat_4 = 5
    model_sj_path_4 = './rnn/sj_5_5_3_2_1-210-17.80.hdf5'
    model_iq_path_4 = './rnn/iq_5_5_3_2_1-126-0.68.hdf5'
    add_4 = 5
    weekPredAfter_4 = 2

    weekConcat_5 = 12
    model_sj_path_5 = './rnn/labelsj32_3000_100_adam_elu_softmax_1sj_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.51_256_0.4_1280.4_64_0.4_12_4_.h5py'
    model_iq_path_5 = './rnn/labeliq32_3000_100_adam_elu_softmax_2iq_256_512_256_1280.5_0.7_0.5_0.332_32_64_320.1_0.5_0.5_0.52_256_0.4_1280.4_64_0.4_12_4_.h5py'
    add_5 = 4 
    weekPredAfter_5 = 1
    
    y_pred_1 = main(model_sj_path_1, model_iq_path_1, add_1, weekConcat_1, weekPredAfter_1)
    y_pred_2 = main(model_sj_path_2, model_iq_path_2, add_2, weekConcat_2, weekPredAfter_2)
    y_pred_3 = main(model_sj_path_3, model_iq_path_3, add_3, weekConcat_3, weekPredAfter_3)
    y_pred_4 = main(model_sj_path_4, model_iq_path_4, add_4, weekConcat_4, weekPredAfter_4)
    y_pred_5 = main(model_sj_path_5, model_iq_path_5, add_5, weekConcat_5, weekPredAfter_5)

    peak = drawPeak()
    y_pred = (y_pred_1 + y_pred_2 + y_pred_3 +  y_pred_5)/4
    
    idx = 0
    i = 0
    while i <= peak[peak.shape[0]-1]:
        if i == peak[idx]:
            y_pred[i] = (y_pred[i] * 4 + y_pred_4[i] * 1)/5
            idx = idx + 1
        i = i + 1

    output = open(prediction_path, 'w')
    output.write('city,year,weekofyear,total_cases\n')
    for i in range(len(y_pred)):
        line = ''
        for j in range(3):
            line += str(test_tags[i,j]) + ','
        tmp = abs(round(float(y_pred[i])))
        line += str(int(tmp)) + '\n'
        output.write(line)
    output.close()
    
    print('Elapse time:', time.time()-start_time, 'seconds\n')
    
    