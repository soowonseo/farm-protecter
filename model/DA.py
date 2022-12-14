# -*- coding: utf-8 -*-
"""DA_제발 돌아가라.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1MRR8WZktvyMysjELg90PKZoDCC1VIXM6

# 필요한 패키지 다운 및 분석 환경 설정
"""

import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
# from torchvision.io import read_image
from PIL import Image
import logging

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
device

from __future__ import print_function, division

from sklearn.preprocessing import LabelEncoder
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import torch.backends.cudnn as cudnn
import numpy as np
import torchvision
from torchvision import datasets, models, transforms
import matplotlib.pyplot as plt
import time
import os
import copy

import torchvision.transforms as transforms

cudnn.benchmark = True
plt.ion()   # interactive mode

from google.colab import drive
drive.mount('/content/drive')

"""# Data Load (by using imageFolder)"""

data_dir = '/content/drive/Shareddrives/2022 데이터 청년 캠퍼스/pest/'

train_data = '/content/drive/Shareddrives/2022 데이터 청년 캠퍼스/pest/train'
test_data = '/content/drive/Shareddrives/2022 데이터 청년 캠퍼스/pest/test'

"""image data 전처리(resize, normalization)"""

data_transforms = {
    'train': transforms.Compose([
        transforms.RandomResizedCrop(84),  #img 사이즈를 변경한다.
        #transforms.Resize(128),              #img 사이즈를 사이즈로 변경한다. 
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.497, 0.529, 0.337], [0.161, 0.157, 0.162])
    ]),
    'test': transforms.Compose([
        transforms.RandomResizedCrop(84),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        #transforms.ToPILImage(),
        #transforms.CenterCrop(),  #가운데 부분을 사이즈 크기로 자른다.
        transforms.Normalize([0.487, 0.529, 0.337], [0.166, 0.159, 0.160])
    ]),
}

"""torch.utils.data.DataLoader (불러온 데이터셋 변수, batch_size=1, shuffle=False, sampler=None,
batch_sampler=None, num_workers=0, collate_fn=None, pin_memory=False, drop_last=False,
timeout=0, worker_init_fn=None, multiprocessing_context=None )


**parameters**
- batch_size : 모델을 한 번 학습시킬 때 몇 개의 데이터를 넣을지 정한다. 1 배치가 끝날때마다 파라미터를 조정한다.

- shuffle : 데이터를 섞을지 정한다.

- num_workers : 몇개의 subprocesses를 가동시킬건지 정한다.

- drop_last : 배치별로 묶고 남은 데이터를 버릴지 (True) 여부를 정한다.

 
"""

image_datasets = {x: datasets.ImageFolder(os.path.join(data_dir, x),
                                          data_transforms[x])
                  for x in ['train', 'test']}
dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=4, shuffle=True, num_workers=4)
              for x in ['train', 'test']}
dataset_sizes = {x: len(image_datasets[x]) for x in ['train', 'test']}
class_names = image_datasets['train'].classes

print("class_names : ", class_names)
print("\n")
print("datasets_sizes : ", dataset_sizes)
print("\n")
print("image_datasets : ", image_datasets)

def imshow(inp, title=None):
    """Imshow for Tensor."""
    inp = inp.numpy().transpose((1, 2, 0))
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    inp = std * inp + mean
    inp = np.clip(inp, 0, 1)
    plt.imshow(inp)
    if title is not None:
        plt.title(title)
    plt.pause(0.001)  # pause a bit so that plots are updated

# Get a batch of training data
inputs, classes = next(iter(dataloaders['train']))

# Make a grid from batch
out = torchvision.utils.make_grid(inputs)

imshow(out, title=[class_names[x] for x in classes])

def visualize_model(model, num_images=6):
    was_training = model.training
    model.eval()
    images_so_far = 0
    fig = plt.figure()

    with torch.no_grad():
        for i, (inputs, labels) in enumerate(dataloaders['test']):
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            _, preds = torch.max(outputs, 1)

            for j in range(inputs.size()[0]):
                images_so_far += 1
                ax = plt.subplot(num_images//2, 2, images_so_far)
                ax.axis('off')
                ax.set_title(f'predicted: {class_names[preds[j]]}')
                imshow(inputs.cpu().data[j])

                if images_so_far == num_images:
                    model.train(mode=was_training)
                    return
        model.train(mode=was_training)

"""# Domain Adaptation"""

from torch.autograd import Function

class GradientReversalFn(Function):
  @staticmethod
  def forward(ctx, x, alpha):
    #store context for backprop
    ctx.alpha=alpha
    
    return x   #forward pass is a no-op

  @staticmethod
  def backward(ctx, grad_output):

    #Backward pass is just to -alpha the gradient
    output= - ctx.alpha * grad_output

    return output, None  #Must return same num as inputs to forward()

"""#### Sequential 만드는 함수

def make_sequential(in_channel, out_channel, *args, **kwargs):

  return nn.Sequential(nn.Conv2d(in_channel, out_channel, *args, **kwargs),
                       nn.BatchNorm2d(out_channel),
                       nn.ReLU(True),
                       nn.MaxPool2d(*args, **kwargs))

# DACNN model
"""

class DACNN(nn.Module):
  def __init__(self):
    super().__init__()

    in_channel=3
    out_channel=3

    #self.layer_size=[in_channel, out_channel]
    #layers= [make_sequential(in_channel, out_channel, kernel_size=5, stride=1, padding=2)
    #                    for in_channel, out_channel in zip(self.layer_size, self.layer_size[1:])]
    #self.feature_extractor_encoder=nn.Sequential(*layers)

    self.feature_extractor = nn.Sequential(
      nn.Conv2d(in_channel,16,kernel_size=3,padding=1,stride=1),    #(28+2p-f)/s+1=26   (img_siz+2*padding-kernelsize)/stride+1
      nn.BatchNorm2d(16), 
      nn.ReLU(True),  
      nn.MaxPool2d(2),  #26/2=13   conv2d/maxpool2d(n)

      nn.Conv2d(16,64,kernel_size=3,padding=1,stride=1),   #(12+2p-f)/s+1=10
      nn.BatchNorm2d(64), 
      nn.ReLU(True),
      nn.MaxPool2d(2),  #10/2=5

      nn.Conv2d(64, 128,kernel_size=3,padding=1,stride=1),   
      nn.BatchNorm2d(128), 
      nn.ReLU(True),
      nn.MaxPool2d(2),  

      nn.Conv2d(128,256,kernel_size=3,padding=1,stride=1),   
      nn.BatchNorm2d(256), 
      nn.ReLU(True),
      nn.MaxPool2d(2), 
      )


    self.num_cnn_features=6400          #input / shape 사이즈 동일해야함.

    self.class_classifier=nn.Sequential(
        nn.Linear(self.num_cnn_features, 256),
        nn.BatchNorm1d(256),
        nn.ReLU(True),

        nn.Linear(256, 84),
        nn.BatchNorm1d(84),
        nn.ReLU(True),
        
        nn.Linear(84,out_channel),
        nn.LogSoftmax(dim=1),
    )

    self.domain_classifier=nn.Sequential(
        nn.Linear(self.num_cnn_features, 84),
        nn.BatchNorm1d(84),
        nn.ReLU(True),

        nn.Linear(84,out_channel),
        nn.LogSoftmax(dim=1),
    )

  def forward(self, x, grl_lamda=1.0):    
    #handle single channel input by expanding the singleton dimention
    x = x.expand(x.data.shape[0], 3, image_size, image_size)
    
    features = self.feature_extractor(x)
    features = features.view(-1, self.num_cnn_features)
    features_grl = GradientReversalFn.apply(features,grl_lamda)
    class_pred = self.class_classifier(features)                # classify on regular features
    domain_pred=self.domain_classifier(features_grl)            # classify on  features after GRL
    
    return class_pred, domain_pred

tr=dataloaders['train']
te=dataloaders['test']

print(type(te))

model=DACNN()


x0_s,y0_s = next(iter(tr))
x0_t,y0_t = next(iter(te))

print('source domain input: ', x0_s.shape, y0_s.shape)
print('target domain input: ', x0_t.shape, y0_t.shape)

image_size=84

yhat0_s_c, yhat0_s_d=model(x0_s)
yhat0_t_x, yhat0_t_d=model(x0_t)

print('yhat0_s_c: \n ', yhat0_s_c, yhat0_s_c.shape)
print('yhat0_t_d: \n ', yhat0_t_d, yhat0_t_d.shape)

"""# Train"""

device='cpu'
device=torch.device(device)

train_dataset=torchvision.datasets.ImageFolder(train_data, transform=data_transforms['train'])
test_dataset= torchvision.datasets.ImageFolder(test_data, transform=data_transforms['test'])

batch_size=3

train_l=torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
test_l= torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=True)

n_epochs=10
in_channel=3
out_channel=3
image_size=84

model=DACNN().to(device)

optimizer=optim.Adam(model.parameters(), lr=1e-3)

# two loss functions 
loss_fn_class=torch.nn.NLLLoss()
loss_fn_domain=torch.nn.NLLLoss()

# train the same num of batches from both dataset
max_batches = min(len(train_dataset), len(test_dataset))
max_batches

def test(dataset):

    #cuda = True
    cudnn.benchmark = True
    batch_size = 128
    #image_size = 84
    grl = 0

    my_net=DACNN()
    my_net = my_net.eval()

    #if cuda:
    #    my_net = my_net.cuda()

    len_dataloader = len(dataset)
    data_target_iter = iter(dataset)

    i = 0
    n_total = 0
    n_correct = 0

    while i < len_dataloader:

        # test model using target data
        data_target = next(data_target_iter)
        t_img, t_label = data_target

        #batch_size = len(t_label)

        input_img = torch.FloatTensor(batch_size, 3, image_size, image_size)
        #print(input_img.shape)
        class_label = torch.LongTensor(batch_size)

        #if cuda:
        #    t_img = t_img.cuda()
        #    t_label = t_label.cuda()
        #    input_img = input_img.cuda()
        #    class_label = class_label.cuda()

        #input_img.resize_as_(t_img).copy_(t_img)
        #class_label.resize_as_(t_label).copy_(t_label)

        class_output, _ = my_net(x=input_img)
        pred = class_output.data.max(1, keepdim=True)[1]
        n_correct += pred.eq(class_label.data.view_as(pred)).cpu().sum()
        n_total += batch_size

        i += 1

    accu = n_correct.data.numpy() * 1.0 / n_total

    print('epoch: %d, accuracy : %f' % (i, accu))

for epoch_idx in range(n_epochs):
  print(f'Epoch {epoch_idx+1:04d}/{n_epochs:04d}', end='\n========================\n')
  #print(f'Epoch {epoch_idx}/{n_epochs - 1}', end='\n========================\n')

  dl_source_iter=iter(train_dataset)
  dl_target_iter=iter(test_dataset)


  for batch_idx in range(max_batches):
    optimizer.zero_grad()

    p=float(batch_idx + epoch_idx* max_batches)/(n_epochs * max_batches)
    grl_lambda=2./(1.+np.exp(-10*p))-1

    # Train: source  domain
    x_s,y_s=next(dl_source_iter)
    y_s_domain=torch.zeros(batch_size, dtype=torch.long)

    class_pred, domain_pred=model(x_s,grl_lambda)
    #loss_s_label=loss_fn_class(class_pred, y_s)
    loss_s_domain=loss_fn_domain(domain_pred, y_s_domain)

    # Train: target domain
    x_t, _ =next(dl_target_iter)
    y_t_domain=torch.ones(batch_size, dtype=torch.long)
    
    _, domain_pred=model(x_t, grl_lambda)
    loss_t_domain=loss_fn_domain(domain_pred, y_t_domain)

    #최적화
    #loss=loss_t_domain+loss_s_domain+loss_s_label
    loss=loss_t_domain+loss_s_domain
    loss.backward()
    optimizer.step()

    print(f'[{batch_idx+1}/{max_batches}]'
          #f'class loss: {loss_s_label.item(): .4f}'
          f's_domain_loss: {loss_s_domain.item(): .4f}    /    t_domain loss: {loss_s_domain.item(): .4f}    /    grl_lambda: {grl_lambda: .3f}'
          )
  print('\n')
  accu_s = test(train_dataset)
  print('Accuracy_s: ', accu_s, '%')
  #print('Accuracy_s: {: .%4f}%'.format(accu_s))
  accu_t = test(test_dataset)
  print('Accuracy_t: ', accu_t, '%')
  #print('Accuracy_t: {: .%4f}%'.format(accu_t))