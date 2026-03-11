class StatestransitionPolicy:
    """集中管理所有的 transition rules"""
    transitionPolicy = {
        "opening": '''
            直接进入ask_intent环节。
        ''',
        "ask_intent":'''
            如果用户有购车意向：进入ask_brand_budget环节，
            无意向的话：进入end环节
        ''',
        "ask_brand_budget":'''
            如果用户清晰表达了喜欢的品牌和购车的预算:进入recommend环节。
            如果用户表达地不清晰：进入ask_brand_budget环节继续追问。
        ''',
        "recommend": '''
            如果用户感兴趣：进入schedule_visit环节，
            不敢兴趣：进入ask_concerns环节。
        ''',
        "ask_concerns":'''
            客户有现实阻碍，钱，没时间，决策权不在客户手上等等：进入PROMOTION环节。
            客户遇到了障碍，但是表达地不清楚，不明确：进入ASK_CONCERNS，追问具体的顾虑是什么
            客户的确不想买车：进入END环节
        ''',
        "promotion":'''
            PROMOTION后仍拒绝，不愿买车:进入END环节。
            PROMOTION后被打动，考虑买车: SCHEDULE_VISIT。
        ''',
        "schedule_visit":'''
            如果客户明确表达了合适可以来点看车或者试驾:进入END环节。
            如果客户未能清晰表达来店的时间：进入schedule_visit环节，重新询问。
        '''
    }
    @classmethod
    def get(cls, state: str) -> str:
        return cls.transitionPolicy[state]