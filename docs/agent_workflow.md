## 汽车销售电话的业务底层逻辑
```
现实中，销售在没一通电话里，其实在做三件事：
1.判断对象是不是潜在客户
2.如果是，能不能推进一小步
3，如果不能，是否有回旋价值
4. 现实电话销售的KPI从不是端到端卖车，而是约到店/试驾
```

## 状态设计
- OPENING: 开场问候
- ASK_INTENT: 询问购车意图
- ASK_BRAND_BUDGET: 询问购车意向品牌和预算
- RECOMMEND: 根据预算，品牌，推荐车型
- ASK_CONCERNS： 如果对推荐的车型不感兴趣，询问购车顾虑
- PROMOTION：介绍购车活动
- SCHEDULE_VISIT：预约线下试车或者进一步见面
- END：结束阶段

## work_flow设计
```
OPENING
  ↓
ASK_INTENT
  ├── 无意向 → END（止损）
  └── 有意向
        ↓
ASK_BRAND_BUDGET
        ├── 信息不清 / 模糊
        │        ↺（追问 / 澄清）
        └── 信息明确
              ↓
RECOMMEND
        ├── 感兴趣
        │      ↓
        │   SCHEDULE_VISIT
        │      ↓
        │     END（成功结束）
        │
        └── 不感兴趣
              ↓
          ASK_CONCERNS
              ├── 有现实阻碍（钱 / 时间 / 家庭）
              │       ↓
              │   PROMOTION
              │       ├── 仍拒绝 → END
              |       └── 被打动 → SCHEDULE_VISIT
              │── 用户的回答不是很清楚，有顾虑但不明确 
              |         ↓
              |     ASK_CONCERNS（继续追问）    
              │
              │
              └── 纯犹豫 / 拖延
                      ↓
                    END（礼貌退出）
```
