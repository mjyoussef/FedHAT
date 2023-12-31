from torch.utils.data import DataLoader, Dataset
from torchvision import datasets
from torchvision.transforms import ToTensor
import torch
import json
import csv
import numpy as np
import os
import argparse

class DatasetSplit(Dataset):
    """An abstract Dataset class wrapped around Pytorch Dataset class.
    """

    def __init__(self, dataset, idxs):
        self.dataset = dataset
        self.idxs = [int(i) for i in idxs]

    def __len__(self):
        return len(self.idxs)

    def __getitem__(self, item):
        image, label = self.dataset[self.idxs[item]]
        return torch.tensor(image), torch.tensor(label)

class AGNEWS(Dataset):
    def __init__(self, label_data_path, alphabet_path, l0 = 1014):
        """Create AG's News dataset object.

        Arguments:
            label_data_path: The path of label and data file in csv.
            l0: max length of a sample.
            alphabet_path: The path of alphabet json file.
        """
        self.label_data_path = label_data_path
        self.l0 = l0
        self.loadAlphabet(alphabet_path)
        self.load(label_data_path)
        
    def __len__(self):
        return len(self.label)

    def __getitem__(self, idx):
        X = self.oneHotEncode(idx)
        y = self.y[idx]
        return X, y

    def loadAlphabet(self, alphabet_path):
        with open(alphabet_path) as f:
            self.alphabet = ''.join(json.load(f))
            self.alphabet_size = len(self.alphabet)

    def load(self, label_data_path, lowercase = True):
        self.label = []
        self.data = []
        with open(label_data_path, 'r') as f:
            rdr = csv.reader(f, delimiter=',', quotechar='"')
            for _, row in enumerate(rdr):
                self.label.append(int(row[0]) - 1)
                txt = ' '.join(row[1:])
                if lowercase:
                    txt = txt.lower()                
                self.data.append(txt)

        self.y = torch.LongTensor(self.label)


    def oneHotEncode(self, idx):
        X = torch.zeros(len(self.alphabet), self.l0)
        sequence = self.data[idx]
        for index_char, char in enumerate(sequence[::-1]):
            if self.char2Index(char) != -1:
                X[self.char2Index(char)][index_char] = 1.0
        return X

    def char2Index(self, character):
        return self.alphabet.find(character)

    def getClassWeight(self):
        num_samples = self.__len__()
        label_set = set(self.label)
        num_class = [self.label.count(c) for c in label_set]
        class_weight = [num_samples/float(self.label.count(c)) for c in label_set]    
        return class_weight, num_class
       
def create_client_config(num_users, dataset, type):
    '''
    config_path: txt file for configs (one for CIFAR-10 and one for AG_NEWS)

    allocates non-iid data samples for each client
    '''
    np.random.seed(int(os.environ['seed']))
    num_shards = num_users * 2
    num_samples = len(dataset) // num_shards
    idx_shard = [i for i in range(num_shards)]
    dict_users = {i: np.array([], dtype=int) for i in range(num_users)}
    idxs = np.arange(len(dataset))
    if (type == 'CIFAR10'):
        labels = np.array(dataset.targets)
    else:
        labels = np.array(dataset.label)
        print(labels)

    # sort by label
    tups = np.vstack((labels, idxs)).T
    tups = tups.tolist()
    tups.sort()
    tups = np.array(tups, dtype=int)
    idxs = tups[:, 1]

    # divide and assign
    for i in range(num_users):
        rand_set = set(np.random.choice(idx_shard, 2, replace=False))
        idx_shard = list(set(idx_shard) - rand_set)
        for rand in rand_set:
            dict_users[i] = np.concatenate((dict_users[i], idxs[rand*num_samples:(rand+1)*num_samples]), axis=0)
    
    return dict_users

def load_client_config(clients_dict, dataset, client_id, bs):
    indices = clients_dict[str(client_id)]
    trainloader = DataLoader(DatasetSplit(dataset, indices), batch_size=bs, shuffle=True)
    return trainloader