# 装箱运费规划器

输入商品长宽高、重量、朝向限制和订单数量，在候选箱型中试出能实际装入的组合，
用 Three.js 展示箱内摆放，并按多个运费方案分别计算费用。

## 简化条件（页面也有标明）

- 仅处理**轴向摆放**的长方体，商品棱与箱体棱平行；
- 商品之间不得重叠、不得超出箱体内尺寸；
- `upright`（保持直立）商品只能在水平面转 90°（高度轴始终竖直）；
  `any` 商品允许全部六种轴向朝向；
- **不考虑支撑力、易碎要求与填充空隙**；
- 求解为启发式（极端点 + 多策略贪心 + 箱型多重集枚举），**不保证全局最低价**。

## 判定口径

- `exceeds_all_boxes`：商品单件在允许朝向下放不进任何箱型，或单件即超过箱型最大毛重——
  这是**确定**超出所有箱型限制；
- `no_solution_found`：商品单件能放进某个箱型，但启发式算法在箱数上限内没找到完整方案——
  **不代表数学上一定无解**，页面与接口都不会把它说成无解。

## 运费计算（每个方案独立计算）

对每个已装箱：

1. 体积重量 = 按箱**外尺寸**体积 ÷ 体积重量除数，向上取整（克）；
2. 毛重 = 箱内商品重量 + 箱重；
3. 计费重量 = max(体积重量, 毛重) 再向上取整到计费步长；
4. 运费 = 计费重量 ÷ 步长 × 每步价格；本箱合计 = 运费 + 箱费。

因为每箱分别向上取整，拆成多箱有时比单箱更便宜；出现这种情况时结果里会给出解释
（`warnings` 字段，页面顶部蓝色提示）。

## 独立校验

`app/validator.py` 不依赖求解器内部实现，从响应原始数据重新推导并检查：
数量对账、朝向合法性、坐标不出界、两两不重叠、毛重上限，以及每个方案的
体积重量/计费重量/运费/合计算术。响应中的 `validator_passed` / `validator_errors`
即校验结论；校验不过时前端会显著标红。

## 技术栈

- 后端：Python 3.11 + FastAPI + SQLite（标准库 `sqlite3`）+ Pydantic v2
- 前端：React 19 + Vite + Three.js（OrbitControls，可旋转/缩放查看）
- 测试：pytest（后端 26 项）、node:test + jsdom（前端 10 项）

## 运行

```bash
# 后端（首次自动建库并写入示例箱型/运费方案）
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" pydantic pytest httpx
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端开发（代理 /api 到 8000）
cd frontend
npm install
npm run dev          # http://localhost:5173

# 前端生产构建（构建后由 FastAPI 在 / 直接托管）
npm run build
```

打开 http://localhost:8000/ 即可使用构建后的页面。SQLite 文件默认在 `data/planner.db`，
可用环境变量 `PLANNER_DB` 覆盖。

## 测试

```bash
.venv/bin/python -m pytest tests/ -q     # 后端
cd frontend && npm test                  # 前端（Three.js 查看器以桩件替代，WebGL 需真实浏览器）
```

## 目录

```
app/
  models.py     Pydantic 接口模型（尺寸整数毫米、重量克）
  db.py         SQLite 建表、示例数据、箱型/方案 CRUD、求解记录
  packing.py    朝向枚举、极端点放置（含投影规则）、多箱搜索、运费算术
  validator.py  独立校验器
  service.py    编排：搜索 → 报价矩阵 → 拆箱解释 → 校验
  main.py       FastAPI 路由与静态托管
frontend/src/
  App.jsx ItemForm.jsx ItemTable.jsx Catalog.jsx Results.jsx
  BoxViewer.jsx geometry.js api.js
tests/          后端 pytest
frontend/tests/ 前端 node:test
```
