# 典型病例原始图像与 ROI 

R2（李嘉泓师兄的部分病例肌肉标签是2脂肪是3，我的话肌肉都是3脂肪都是2，所以导出截图的时候有些ROI会标错）

## 1. 入选病例总览

| 影像号 | R1 序列 | R2 序列 | 肿瘤 Dice | 序列是否一致 |
|---|---:|---|---|---:|---|
| IMG-97E9F2C29B | 5 Ax T2 frFSE | 7 Cor T2 frFSE | 0.3969 | 标准化序列名不同；图像网格不同 |
| IMG-182FA24923 | 5 OAx T2 FRFSE | 5 OAx T2 FRFSE | 0.7347 | 同一序列 |
| IMG-893073F906 | 5 Ax T2 FRFSE | 8 COR T2 FRFSE | 0.6576 | 标准化序列名不同；图像网格不同 |
| IMG-AF5A3DA75D | 6 Ax T2 frFSE | 5 Ax T2 frFSE | 0.7050 | 标准化序列名不同；图像网格不同 |
| IMG-16B3264BD9 | 6 OAx T2 FRFSE | 6 OAx T2 FRFSE | 0.3709 | 同一序列 |
| IMG-ECE86CBFCB | 5 OAx T2 FRFSE | 5 OAx T2 FRFSE | 0.4709 | 同一序列 |
| IMG-825C59B3C8 | 5 OAx T2 FRFSE | 5 OAx T2 FRFSE | 0.8885 | 同一序列 |
| IMG-1815129EC4 | 7 OAx T2 FRFSE 16fov | 7 OAx T2 FRFSE 16fov | 0.8582 | 同一序列 |

## 2. 逐例截图

### IMG-97E9F2C29B（R1/R2序列不一致）

- R1 序列：`5 Ax T2 frFSE`
- R2 序列：`7 Cor T2 frFSE`
- 肿瘤 Dice：**0.3969**
- 序列判定：标准化序列名不同；图像网格不同

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 24/40 | ![IMG-97E9F2C29B R1 t](IMG-97E9F2C29B_R1_t.png) |
| `f`（脂肪） | 27/40 | ![IMG-97E9F2C29B R1 f](IMG-97E9F2C29B_R1_f.png) |
| `m`（肌肉） | 12/40 | ![IMG-97E9F2C29B R1 m](IMG-97E9F2C29B_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t_f`（肿瘤、脂肪） | 20/24 | ![IMG-97E9F2C29B R2 t_f](IMG-97E9F2C29B_R2_t_f.png) |
| `m`（肌肉） | 21/24 | ![IMG-97E9F2C29B R2 m](IMG-97E9F2C29B_R2_m.png) |

### IMG-182FA24923（R1/R2序列不一致）

- R1 序列：`5 OAx T2 FRFSE`
- R2 序列：`5 OAx T2 FRFSE`
- 肿瘤 Dice：**0.7347**
- 序列判定：一致

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 11/24 | ![IMG-182FA24923 R1 t](IMG-182FA24923_R1_t.png) |
| `f`（脂肪） | 8/24 | ![IMG-182FA24923 R1 f](IMG-182FA24923_R1_f.png) |
| `m`（肌肉） | 24/24 | ![IMG-182FA24923 R1 m](IMG-182FA24923_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 10/24 | ![IMG-182FA24923 R2 t](IMG-182FA24923_R2_t.png) |
| `f`（脂肪） | 18/24 | ![IMG-182FA24923 R2 f](IMG-182FA24923_R2_f.png) |
| `m`（肌肉） | 15/24 | ![IMG-182FA24923 R2 m](IMG-182FA24923_R2_m.png) |

### IMG-893073F906（R1/R2序列不一致）

- R1 序列：`5 Ax T2 FRFSE`
- R2 序列：`8 COR T2 FRFSE`
- 肿瘤 Dice：**0.6576**
- 序列判定：标准化序列名不同；图像网格不同

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 26/40 | ![IMG-893073F906 R1 t](IMG-893073F906_R1_t.png) |
| `f`（脂肪） | 27/40 | ![IMG-893073F906 R1 f](IMG-893073F906_R1_f.png) |
| `m`（肌肉） | 29/40 | ![IMG-893073F906 R1 m](IMG-893073F906_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 24/40 | ![IMG-893073F906 R2 t](IMG-893073F906_R2_t.png) |
| `f_m`（脂肪、肌肉） | 22/40 | ![IMG-893073F906 R2 f_m](IMG-893073F906_R2_f_m.png) |

### IMG-AF5A3DA75D（R1/R2序列不一致）

- R1 序列：`6 Ax T2 frFSE`
- R2 序列：`5 Ax T2 frFSE`
- 肿瘤 Dice：**0.7050**
- 序列判定：标准化序列名不同；图像网格不同

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 14/20 | ![IMG-AF5A3DA75D R1 t](IMG-AF5A3DA75D_R1_t.png) |
| `f`（脂肪） | 11/20 | ![IMG-AF5A3DA75D R1 f](IMG-AF5A3DA75D_R1_f.png) |
| `m`（肌肉） | 5/20 | ![IMG-AF5A3DA75D R1 m](IMG-AF5A3DA75D_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t_m`（肿瘤、肌肉） | 18/40 | ![IMG-AF5A3DA75D R2 t_m](IMG-AF5A3DA75D_R2_t_m.png) |
| `f`（脂肪） | 12/40 | ![IMG-AF5A3DA75D R2 f](IMG-AF5A3DA75D_R2_f.png) |

### IMG-16B3264BD9（同序列肿瘤Dice最低）

- R1 序列：`6 OAx T2 FRFSE`
- R2 序列：`6 OAx T2 FRFSE`
- 肿瘤 Dice：**0.3709**
- 序列判定：同一序列

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 12/20 | ![IMG-16B3264BD9 R1 t](IMG-16B3264BD9_R1_t.png) |
| `f`（脂肪） | 13/20 | ![IMG-16B3264BD9 R1 f](IMG-16B3264BD9_R1_f.png) |
| `m`（肌肉） | 1/20 | ![IMG-16B3264BD9 R1 m](IMG-16B3264BD9_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 12/20 | ![IMG-16B3264BD9 R2 t](IMG-16B3264BD9_R2_t.png) |
| `f`（脂肪） | 5/20 | ![IMG-16B3264BD9 R2 f](IMG-16B3264BD9_R2_f.png) |
| `m`（肌肉） | 14/20 | ![IMG-16B3264BD9 R2 m](IMG-16B3264BD9_R2_m.png) |

### IMG-ECE86CBFCB（同序列肿瘤Dice最低）

- R1 序列：`5 OAx T2 FRFSE`
- R2 序列：`5 OAx T2 FRFSE`
- 肿瘤 Dice：**0.4709**
- 序列判定：同一序列

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 9/18 | ![IMG-ECE86CBFCB R1 t](IMG-ECE86CBFCB_R1_t.png) |
| `f`（脂肪） | 6/18 | ![IMG-ECE86CBFCB R1 f](IMG-ECE86CBFCB_R1_f.png) |
| `m`（肌肉） | 13/18 | ![IMG-ECE86CBFCB R1 m](IMG-ECE86CBFCB_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t_m`（肿瘤、肌肉） | 16/18 | ![IMG-ECE86CBFCB R2 t_m](IMG-ECE86CBFCB_R2_t_m.png) |
| `f`（脂肪） | 9/18 | ![IMG-ECE86CBFCB R2 f](IMG-ECE86CBFCB_R2_f.png) |

### IMG-825C59B3C8（同序列肿瘤Dice最高）

- R1 序列：`5 OAx T2 FRFSE`
- R2 序列：`5 OAx T2 FRFSE`
- 肿瘤 Dice：**0.8885**
- 序列判定：同一序列

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 12/18 | ![IMG-825C59B3C8 R1 t](IMG-825C59B3C8_R1_t.png) |
| `f`（脂肪） | 15/18 | ![IMG-825C59B3C8 R1 f](IMG-825C59B3C8_R1_f.png) |
| `m`（肌肉） | 17/18 | ![IMG-825C59B3C8 R1 m](IMG-825C59B3C8_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 12/18 | ![IMG-825C59B3C8 R2 t](IMG-825C59B3C8_R2_t.png) |
| `f`（脂肪） | 5/18 | ![IMG-825C59B3C8 R2 f](IMG-825C59B3C8_R2_f.png) |
| `m`（肌肉） | 14/18 | ![IMG-825C59B3C8 R2 m](IMG-825C59B3C8_R2_m.png) |

### IMG-1815129EC4（同序列肿瘤Dice最高）

- R1 序列：`7 OAx T2 FRFSE 16fov`
- R2 序列：`7 OAx T2 FRFSE 16fov`
- 肿瘤 Dice：**0.8582**
- 序列判定：同一序列

#### R1

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 1/20 | ![IMG-1815129EC4 R1 t](IMG-1815129EC4_R1_t.png) |
| `f`（脂肪） | 9/20 | ![IMG-1815129EC4 R1 f](IMG-1815129EC4_R1_f.png) |
| `m`（肌肉） | 8/20 | ![IMG-1815129EC4 R1 m](IMG-1815129EC4_R1_m.png) |

#### R2

| 最大项 | 层面 | 截图（含该层全部 ROI） |
|---|---:|---|
| `t`（肿瘤） | 1/20 | ![IMG-1815129EC4 R2 t](IMG-1815129EC4_R2_t.png) |
| `f`（脂肪） | 6/20 | ![IMG-1815129EC4 R2 f](IMG-1815129EC4_R2_f.png) |
| `m`（肌肉） | 2/20 | ![IMG-1815129EC4 R2 m](IMG-1815129EC4_R2_m.png) |

