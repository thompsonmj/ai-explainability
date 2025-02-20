"""
Train latent classifier on given VAE model
"""

from argparse import ArgumentParser

import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from torchvision.datasets import MNIST
from torchvision.transforms import ToTensor

from PIL import Image

from models import ImageClassifier
from logger import Logger

def load_data():
    train_dset = MNIST(root="data", train=True, transform=ToTensor(), download=True)
    test_dset = MNIST(root="data", train=False, transform=ToTensor())
    train_dloader = DataLoader(train_dset, batch_size=4, shuffle=True)
    test_dloader = DataLoader(test_dset, batch_size=4, shuffle=False)

    return train_dloader, test_dloader

def get_args():
    parser = ArgumentParser()
    parser.add_argument('--epochs', type=int, default=20)
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--output_dir', type=str, default="output")
    parser.add_argument('--exp_name', type=str, default="img_classifier")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    train_dloader, test_dloader = load_data()

    classifier = ImageClassifier(10)
    total_params = 0
    total_params += sum(p.numel() for p in classifier.parameters() if p.requires_grad)

    logger = Logger(args.output_dir, args.exp_name)

    logger.log(f"Total trainable parameters: {total_params}")
    classifier.cuda()

    class_loss_fn = nn.CrossEntropyLoss()
    params = list(classifier.parameters())
    optimizer = torch.optim.Adam(params, lr=args.lr)

    for epoch in range(args.epochs):
        total_loss = 0
        correct = 0
        total = 0
        classifier.train()
        for imgs, lbls in train_dloader:
            imgs = imgs.cuda()
            lbls = lbls.cuda()

            out = classifier(imgs)
            loss = class_loss_fn(out, lbls)

            _, preds = torch.max(out, dim=1)

            correct += (preds == lbls).sum().item()
            total += len(imgs)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        logger.log(f"Epoch: {epoch+1} | Class Loss: {total_loss} | Train Accuracy: {round(correct/total, 4)}")

        total_loss = 0
        correct = 0
        total = 0
        classifier.eval()
        with torch.no_grad():
            for imgs, lbls in test_dloader:
                imgs = imgs.cuda()
                lbls = lbls.cuda()

                out = classifier(imgs)

                _, preds = torch.max(out, dim=1)

                correct += (preds == lbls).sum().item()
                total += len(imgs)

            logger.log(f"Epoch: {epoch+1} | Test Accuracy: {round(correct/total, 4)}")

        torch.save(classifier.state_dict(), f"{logger.get_path()}/img_classifier.pt")
