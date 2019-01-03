import torch
import numpy as np
import gensim
import os
from gensim.scripts.glove2word2vec import glove2word2vec
# from sklearn.metrics import average_precision_score

def loadEmbed(file, embed_size, vocab_size, word2idx=None, Debug=True):
    # read pretrained word2vec, convert to floattensor
    if(Debug):
        print("[WARN] load randn embedding for DEBUG")
        embed = np.random.rand(vocab_size, embed_size)
        return torch.FloatTensor(embed)

    #load pretrained model
    else:
        embed_matrix = np.zeros([len(word2idx), embed_size])
        print("[Info] load pre-trained word2vec embedding")
        sub_dir = "/".join(file.split("/")[:-1])
        if "glove" in file:
            word2vec_file = ".".join(file.split("/")[-1].split(".")[:-1])+"word2vec"+".txt"
            if word2vec_file not in os.listdir(sub_dir):
                glove2word2vec(file, os.path.join(sub_dir, word2vec_file))
            file = os.path.join(sub_dir, word2vec_file)

        model = gensim.models.KeyedVectors.load_word2vec_format(file,
                                                                binary=False)
        print("[Info] Load glove finish")

        for word, i in word2idx.items():
            if word in model.vocab:
                embed_matrix[i] = model.word_vec(word)

        weights = torch.FloatTensor(embed_matrix)

        return weights

# def mAP(pred, label):
#     #label is binary
#
#     return average_precision_score(label, pred)

def Accuracy(pred, label):
    target = 0
    zero_count = 0
    one_count = 0
    assert len(pred) == len(label),"length not equal"
    for i in range(len(pred)):
        if pred[i] == 0:
            zero_count += 1
        elif pred[i] == 1:
            one_count += 1
        if pred[i] == label[i]:
            target += 1
    return target * 1.0 / len(pred), zero_count / len(pred), one_count / len(pred)
