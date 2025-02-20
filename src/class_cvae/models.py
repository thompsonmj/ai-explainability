import math

import torch
import torch.nn as nn

class ImageClassifier(nn.Module):
    def __init__(self, class_num=10):
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=10, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.block2 = nn.Sequential(
            nn.Conv2d(in_channels=10, out_channels=20, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.linear = nn.Linear(20*7*7, class_num)

    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        x = x.view(x.shape[0], -1)
        out = self.linear(x)
        return out


class Encoder(nn.Module):
    def __init__(self, num_features=20, use_sigmoid=False):
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=10, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.block2 = nn.Sequential(
            nn.Conv2d(in_channels=10, out_channels=20, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.linear_mean = nn.Linear(20*7*7, num_features)
        self.linear_std = nn.Linear(20*7*7, num_features)
        self.sigmoid = nn.Sigmoid()
        self.use_sigmoid = use_sigmoid

    def forward(self, x, stats=False):
        x = self.block1(x)
        x = self.block2(x)
        x = x.view(x.shape[0], -1)
        mu = self.linear_mean(x)
        std = self.linear_std(x)

        z = mu + std * torch.normal(mean=0, std=1, size=std.shape).cuda()

        if self.use_sigmoid:
            z = self.sigmoid(z)
        
        if stats:
            return z, mu, std

        return z

class Decoder(nn.Module):
    def __init__(self, num_features=20):
        super().__init__()
        self.linear = nn.Sequential(
            nn.Linear(num_features, 20*7*7),
            nn.ReLU()
        )
        self.convT1 = nn.Sequential(
            nn.ConvTranspose2d(in_channels=20, out_channels=10, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
        )

        self.convT2 = nn.Sequential(
            nn.ConvTranspose2d(in_channels=10, out_channels=1, kernel_size=2, stride=2, padding=0),
            nn.Tanh()
        )

    def forward(self, x):
        x = self.linear(x)
        x = x.view(x.shape[0], 20, -1)
        size = int(math.sqrt(x.shape[2]))
        x = x.view(x.shape[0], x.shape[1], size, size)
        x = self.convT1(x)
        x = self.convT2(x)
        x = ((x + 1) / 2)
        return x


class Classifier(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.linear = nn.Linear(in_c, out_c)

    def forward(self, x):
        return self.linear(x)


class SimpleEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv2d(in_channels=1, out_channels=10, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.block2 = nn.Sequential(
            nn.Conv2d(in_channels=10, out_channels=20, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )

        self.linear = nn.Linear(20*7*7, 7)

    def forward(self, x, stats=False):
        x = self.block1(x)
        x = self.block2(x)
        x = x.view(x.shape[0], -1)
        return nn.Sigmoid()(self.linear(x))

class HandCraftedMNISTDecoder(nn.Module):
    def __init__(self):
        super().__init__()

    def forward(self, x):
        batch = len(x)
        base = torch.zeros(batch, 1, 28, 28).cuda() # Blank Images
        base[:, 0, 2:4, 6:22] = x[:, 0].view(batch, 1).repeat(1, 2*16).view(batch, 2, 16) # Top Line
        base[:, 0, 13:15, 6:22] = x[:, 1].view(batch, 1).repeat(1, 2*16).view(batch, 2, 16) # Middle Line
        base[:, 0, 24:26, 6:22] = x[:, 2].view(batch, 1).repeat(1, 2*16).view(batch, 2, 16) # Bottom Line
        base[:, 0, 4:13, 4:6] = x[:, 3].view(batch, 1).repeat(1, 2*9).view(batch, 9, 2) # Top Left Line
        base[:, 0, 4:13, 22:24] = x[:, 4].view(batch, 1).repeat(1, 2*9).view(batch, 9, 2) # Top Right Line
        base[:, 0, 15:24, 4:6] = x[:, 5].view(batch, 1).repeat(1, 2*9).view(batch, 9, 2) # Bottom Left Line
        base[:, 0, 15:24, 22:24] = x[:, 6].view(batch, 1).repeat(1, 2*9).view(batch, 9, 2) # Bottom Right Line

        return base