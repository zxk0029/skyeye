<!--
parent:
  order: false
-->

<div align="center">
  <h1> skyeye 项目 </h1>
</div>

<div align="center">
  <a href="https://github.com/SavourDao/skyeye/releases/latest">
    <img alt="Version" src="https://img.shields.io/github/tag/SavourDao/skyeye.svg" />
  </a>
  <a href="https://github.com/SavourDao/skyeye/blob/main/LICENSE">
    <img alt="License: Apache-2.0" src="https://img.shields.io/github/license/SavourDao/skyeye.svg" />
  </a>
</div>

skyeyee 是 Savour 项目的行情聚合器，聚合了中心化交易和去中心化交易的行情，使用 python 编写，提供 grpc 接口给上层服务访问

**注意**: 需要 [python3.8+](https://www.python.org/)

## 安装

### 安装依赖
```bash
pip3 install -r  requirements.txt
```

### 启动程序
```bash
python3 manager runserver
```

## 贡献代码

### 第一步： fork 仓库

将 skyeye fork 到您自己的代码仓库

### 第二步： clone 您自己仓库的代码

```bash
git@github.com:guoshijiang/skyeye.git
```

### 第三步：建立分支编写提交代码

```bash
git branch -C xxx
git checkout xxx
编写您的代码
git add .
git commit -m "xxx"
git push origin xxx
```

### 第四步：提交 PR

到你的 github 上面有一个 pr, 提交到 skyeye 代码库


### 第五步：review 完成

待 skyeye 代码维护者 review 通过之后代码会合并到 skyeye 库中，至此，您的 PR 就提交完成了 
