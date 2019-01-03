import argparse
import math
import time
from tqdm import tqdm
from tqdm import trange
#pytorch import
import torch
import torch.nn as nn
import torch.nn.functional as F
from attention.Model import HybridAttentionModel
import numpy as np
from dataset import QuestionAnswerUser, paired_collate_fn
from attention.Utils import Accuracy


#grid search for paramter
from sklearn.model_selection import ParameterGrid
from sklearn.model_selection import ParameterGrid
from visualization.logger import Logger
from CNTN.Model import  CNTN


info = {}
logger = Logger('./logs')
i_flag = 0
def prepare_dataloaders(data, opt):
    # ========= Preparing DataLoader =========#

    train_loader = torch.utils.data.DataLoader(
        QuestionAnswerUser(
            word2idx=data['dict'],
            word_insts=data['content'],
            user=data['user'],
            question_answer_user=data['question_answer_user_train'],
            max_u_len=opt.max_u_len
        ),
        num_workers=2,
        batch_size=opt.batch_size,
        collate_fn=paired_collate_fn,
        shuffle=True)

    val_loader = torch.utils.data.DataLoader(
        QuestionAnswerUser(
            word2idx=data['dict'],
            word_insts=data['content'],
            user=data['user'],
            question_answer_user=data['question_answer_user_val'],
            max_u_len=opt.max_u_len
        ),
        num_workers=2,
        batch_size=opt.batch_size,
        collate_fn=paired_collate_fn,
        shuffle=True)

    test_loader = torch.utils.data.DataLoader(
        QuestionAnswerUser(
            word2idx=data['dict'],
            word_insts=data['content'],
            user=data['user'],
            question_answer_user=data['question_answer_user_test'],
            max_u_len=opt.max_u_len
        ),
        num_workers=2,
        batch_size=opt.batch_size,
        collate_fn=paired_collate_fn,
        shuffle=True)
    return train_loader, val_loader, test_loader


def train_epoch(model, data, optimizer, args, epoch):
    model.train()
    loss_fn = nn.NLLLoss()
    l = len(data)
    i = 0
    t = 0
    t_max = len(data)
    for batch in tqdm(
        data, mininterval=2, desc=' --(training)--',leave=True
    ):
        q_iter, a_iter, u_iter, gt_iter = map(lambda x: x.to(args.device), batch)
        args.max_q_len = q_iter.shape[1]
        args.max_a_len = a_iter.shape[1]
        args.batch_size = q_iter.shape[0]
        optimizer.zero_grad()
        result, acc = model(q_iter, a_iter, u_iter, (epoch * l + i) * t_max + t)
        loss = loss_fn(result, gt_iter)
        logger.scalar_summary("train_loss",loss.item(), (epoch * l + i) * t_max + t)
        t = t + 1
        loss.backward()
        optimizer.step()

    # for tag, value in model.named_parameters():
    #     if value.grad is None:
    #         continue
    #     tag = tag.replace('.', '/')
    #     logger.histo_summary(tag, value.cpu().detach().numpy(), epoch * l + i)
    #     logger.histo_summary(tag + '/grad', value.grad.cpu().numpy(), epoch * l + i)

    i += 1



def eval_epoch(model, data, args, epoch):
    model.eval()
    pred_all = []
    label_all = []
    loss_fn = nn.NLLLoss()
    loss = 0
    with torch.no_grad():
        for batch in tqdm(
            data, mininterval=2, desc="  ----(validation)----  ", leave=True
        ):
            q_val, a_val, u_val, gt_val = map(lambda x: x.to(args.device), batch)
            args.max_q_len = q_val.shape[1]
            args.max_a_len = a_val.shape[1]
            args.batch_size = gt_val.shape[0]
            result, predict = model(q_val, a_val, u_val)
            loss += loss_fn(result, gt_val)
            pred_all.append(predict)
            label_all.append(gt_val)
    pred_all = torch.cat(pred_all)
    label_all = torch.cat(label_all)
    accuracy, zero_count, one_count = Accuracy(pred_all, label_all)
    info['eval_loss'] = loss.item()
    info['eval_accuracy'] = accuracy
    info['zero_count'] = zero_count
    info['one_count'] = one_count
    for tag, value in info.items():
        logger.scalar_summary(tag, value, epoch)
    print("[Info] Accuacy: {}; {} samples, {} correct prediction".format(accuracy, len(pred_all), len(pred_all) * accuracy))
    return loss, accuracy



def grid_search(params_dic):
    '''

    :param params_dic: similar to {"conv_size":[0,1,2], "lstm_hiden_size":[1,2,3]}
    :return: iter {"conv_size":1, "lstm_hidden_size":1}
    '''
    grid_parameter = ParameterGrid(params_dic)
    parameter_list = []
    for params in grid_parameter:
        params_dic_result = {}
        for key in params_dic.keys():
            params_dic_result[key] = params[key]
        parameter_list.append(params_dic_result)
    return parameter_list



def train(args, train_data, val_data, word2idx,test_data):
    # if (args.model == 1):
    model = HybridAttentionModel(args, word2idx).to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    # elif(args.model == 2):
    #     model = CNTN(args, word2idx).to(args.device)
    #     optimizer = torch.optim.Adagrad(model.parameters(), lr=args.lr,weight_decay=args.weight_decay)

    #TODO: Early stopping
    for epoch_i in range(args.epoch):
        print("[ Epoch " , epoch_i ," ]")
        train_epoch(model, train_data, optimizer, args, epoch_i)


        val_loss, accuracy_val = eval_epoch(model, val_data, args, epoch_i)
        print("[Info] Val Loss: {}, accuracy: {}".format(val_loss, accuracy_val))
        # test_loss, accuracy_test = eval_epoch(model, test_data, args, epoch_i)
        # print("[Info] Test Loss: {}, accuracy: {}".format(test_loss, accuracy_test))







def main():
    ''' setting '''
    parser = argparse.ArgumentParser()

    parser.add_argument("-epoch",type=int, default=60)
    parser.add_argument("-log", default=None)
    # load data
    # parser.add_argument("-data",required=True)
    parser.add_argument("-no_cuda", action="store_false")
    parser.add_argument("-lr", type=float, default=0.3)
    # 1-UIA-LSTM-CNN; 2-CNTN
    parser.add_argument("-model",type=int,default=1)
    parser.add_argument("-max_q_len", type=int, default=60)
    parser.add_argument("-max_a_len", type=int, default=60)
    parser.add_argument("-max_u_len", type=int, default=200)
    parser.add_argument("-vocab_size", type=int, default=30000)
    parser.add_argument("-embed_size", type=int, default=100)
    parser.add_argument("-lstm_hidden_size",type=int, default=128)
    parser.add_argument("-bidirectional", action="store_true")
    parser.add_argument("-class_kind", type=int, default=2)
    parser.add_argument("-embed_fileName",default="data/glove/glove.6B.100d.txt")
    parser.add_argument("-batch_size", type=int, default=64)
    parser.add_argument("-lstm_nulrm_layers", type=int, default=1)
    parser.add_argument("-drop_out_lstm", type=float, default=0.3)
    # conv parameter
    parser.add_argument("-in_channels", type=int, default=1)
    parser.add_argument("-out_channels", type=int, default=20)
    parser.add_argument("-kernel_size", type=int, default=3)


    args = parser.parse_args()
    #===========Load DataSet=============#


    args.data="data/store.torchpickle"
    #===========Prepare model============#
    args.cuda =  args.no_cuda
    args.device = torch.device('cuda' if args.cuda else 'cpu')
    print("cuda : {}".format(args.cuda))
    args.DEBUG=False
    data = torch.load(args.data)
    word2ix = data['dict']
    train_data, val_data, test_data = prepare_dataloaders(data, args)
    #grid search
    # if args.model == 1:
    paragram_dic = {"lstm_hidden_size":[32, 64, 128, 256, 512],
                   "lstm_num_layers":[2,3,4],
                   "kernel_size":[3,4, 5],
                 "drop_out_lstm":[0.5],
                 "drop_out_cnn":[0.5],
                    "lr":[1e-4, 1e-3, 1e-2]
                    }
    # elif args.model == 2:
    #     paragram_dic = {}
    # else:
    #     paragram_dic = {}
    pragram_list = grid_search(paragram_dic)
    args_dic = vars(args)
    for paragram in pragram_list:
        for key, value in paragram.items():
            print("Key: {}, Value: {}".format(key, value))
            args_dic[key] = value
        args.out_channels = args.lstm_hidden_size
        train(args, train_data, val_data, word2ix, test_data)
if __name__ == '__main__':
    main()




