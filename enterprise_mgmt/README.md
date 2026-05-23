企业内部管理系统

安装运行：
```
# 1. 解压后进入目录
cd enterprise_mgmt

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python main.py
```

说明：首次运行自动建库建表，预置 5 个部门，SQLite 文件生成在项目根目录 enterprise.db。
