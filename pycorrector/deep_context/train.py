# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""

import os
import sys
import time

import numpy as np
import torch
from torch import optim

sys.path.append('../..')
from pycorrector.deep_context import config
from pycorrector.deep_context.data_reader import write_config
from pycorrector.deep_context.model import Context2vec
from pycorrector.deep_context.dataset import Dataset


def train(train_path,
          model_path,
          vocab_path,
          use_mlp=True,
          batch_size=64,
          epochs=3,
          word_embed_size=200,
          hidden_size=200,
          learning_rate=0.0001,
          n_layers=1,
          min_freq=1,
          dropout=0.0,
          gpu_id=0):
    use_cuda = torch.cuda.is_available() and gpu_id > -1
    device = torch.device('cpu')
    if use_cuda:
        device = torch.device('cuda:{}'.format(gpu_id))
        print("use gpu, gpu_id={}".format(gpu_id))

    if not os.path.isfile(train_path):
        raise FileNotFoundError

    print('Loading input file')
    dataset = Dataset(train_path,
                      batch_size,
                      min_freq,
                      device,
                      vocab_path)
    counter = np.array([dataset.word_freqs[word] for word in dataset.vocab_2_ids])
    model = Context2vec(vocab_size=len(dataset.vocab_2_ids),
                        counter=counter,
                        word_embed_size=word_embed_size,
                        hidden_size=hidden_size,
                        n_layers=n_layers,
                        use_mlp=use_mlp,
                        dropout=dropout,
                        pad_index=dataset.pad_index,
                        device=device,
                        inference=False).to(device)
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)

    print('batch_size:', batch_size, 'epochs:', epochs, 'word_embed_size:', word_embed_size, 'hidden_size:',
          hidden_size, 'device:', device)
    print('model:', model)

    # save model config
    output_config_file = model_path + '.config.json'
    write_config(output_config_file,
                 vocab_size=len(dataset.vocab_2_ids),
                 word_embed_size=word_embed_size,
                 hidden_size=hidden_size,
                 n_layers=n_layers,
                 use_mlp=use_mlp,
                 dropout=dropout,
                 pad_index=dataset.pad_index,
                 pad_token=dataset.pad_token,
                 unk_token=dataset.unk_token,
                 sos_token=dataset.sos_token,
                 eos_token=dataset.eos_token,
                 learning_rate=learning_rate
                 )

    interval = 1e5
    best_loss = 1e3
    print("train start...")
    for epoch in range(epochs):
        begin_time = time.time()
        cur_at = begin_time
        total_loss = 0.0
        word_count = 0
        next_count = interval
        last_accum_loss = 0.0
        last_word_count = 0
        cur_loss = 0
        for it, (mb_x, mb_x_len) in enumerate(dataset.train_data):
            sentence = torch.from_numpy(mb_x).to(device).long()
            sentence_len = torch.from_numpy(mb_x_len).to(device).long()

            target = sentence[:, 1:-1]
            if target.size(0) == 0:
                continue
            optimizer.zero_grad()
            loss = model(sentence, target)
            loss.backward()
            optimizer.step()
            total_loss += loss.data.mean()

            minibatch_size, sentence_length = target.size()
            word_count += minibatch_size * sentence_length
            accum_mean_loss = float(total_loss) / word_count if total_loss > 0.0 else 0.0
            cur_mean_loss = (float(total_loss) - last_accum_loss) / (word_count - last_word_count)
            cur_loss = cur_mean_loss
            if word_count >= next_count:
                now = time.time()
                duration = now - cur_at
                throuput = float((word_count - last_word_count)) / (now - cur_at)
                print('{} words, {:.2f} sec, {:.2f} words/sec, {:.4f} accum_loss/word, {:.4f} cur_loss/word'
                      .format(word_count, duration, throuput, accum_mean_loss, cur_mean_loss))
                next_count += interval
                cur_at = now
                last_accum_loss = float(total_loss)
                last_word_count = word_count

        # find best model
        is_best = cur_loss < best_loss
        best_loss = min(cur_loss, best_loss)
        print('epoch:[{}/{}], total_loss:[{}], best_cur_loss:[{}]'
              .format(epoch + 1, epochs, total_loss.item(), best_loss))
        if is_best:
            save_checkpoint(model, optimizer, model_path)
            print('epoch:{}, save new bert model:{}'.format(epoch + 1, model_path))


def save_checkpoint(model, optimizer, model_path):
    torch.save(model.state_dict(), model_path)
    torch.save(optimizer.state_dict(), model_path + '_optim')


if __name__ == "__main__":
    train(config.train_path,
          config.model_path,
          config.vocab_path,
          config.use_mlp,
          config.batch_size,
          config.epochs,
          config.word_embed_size,
          config.hidden_size,
          config.learning_rate,
          config.n_layers,
          config.min_freq,
          config.dropout,
          config.gpu_id
          )
