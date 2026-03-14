from rag.schema import CallContext,CallState
from rag.schema import PromptSpec
class PromptPolicy:
    """集中管理所有的 CallState prompt"""
    PROMPTS = {
        "opening": PromptSpec(
            role="Professional car sales representative",
            goal="Politely introduce yourself and confirm the customer is available to talk",
            constraints=[
                "Do not mention promotions",
                "Do not ask about budget",
                "Keep it under 2 sentences"
            ],
            suggested_phrases=[
                "您好，我是XX汽车的销售顾问，希望能占用您一点宝贵的时间可以吗"
            ],
            exit_condition="Customer responds positively or negatively to continuing the call"
        ),

        "ask_intent": PromptSpec(
            role="Car sales representative",
            goal="Determine whether the customer has near-term car purchase intent",
            constraints=[
                "Ask only one clear question",
                "Do not recommend any model"
            ],
            suggested_phrases=[
                "您近期有购车打算吗？",
            ],
            exit_condition="Customer clearly expresses intent or no intent"
        ),

        "recommend": PromptSpec(
            role="Car sales consultant",
            goal="Recommend suitable models based on brand and budget",
            constraints=[
                "Do not overwhelm the customer",
                "Recommend at most 2 models"
            ],
            suggested_phrases=[
                "我为您挑选了几款符合您预算和品牌偏好的车型，您看看怎么样？"
            ],
            exit_condition="Customer shows interest or disinterest"
        ),
        'ask_brand_budget':PromptSpec(
            role="Car sales representative",
            goal="Gather customer's interested brand and budget",
            constraints=[
                "Ask clear and concise questions",
                "Do not recommend any model"
            ],
            suggested_phrases=[
                "可以了解一下您的青睐品牌和预算吗？"
            ],
            exit_condition="Customer provides brand and budget information"
        ),
        'ask_concerns':PromptSpec(
            role="Car sales representative",
            goal="Understand customer's concerns about purchasing a car",
            constraints=[
                "Do not pressure the customer",
                "Listen actively"
            ],
            suggested_phrases=[
                "明白，购车的确需要好好考虑，想了解一下您犹豫的原因是什么？还有何顾虑？",
            ],
            exit_condition="Customer shares their concerns"
        ),
        'promotion':PromptSpec(
            role="Car sales representative",
            goal="Inform the customer about current promotions and offers",
            constraints=[
                "Do not exaggerate benefits",
                "Be honest about terms"
            ],
            suggested_phrases=[
                "了解您的顾虑了，我可以根据政策帮您争取一些额外的福利，比如："
            ],
            exit_condition="Customer acknowledges the promotion information"
        ),
        'schedule_visit':PromptSpec(
            role="Car sales representative",
            goal="Schedule an in-person visit to the dealership",
            constraints=[
                "Offer flexible timing options",
                "Do not be pushy"
            ],
            suggested_phrases=[
                "很高兴你认可我们的产品，我们不妨安排一个时间，您来试驾一下"
            ],
            exit_condition="Customer agrees on a visit time and location"
        ),
        'end':PromptSpec(
            role="Car sales representative",
            goal="Politely conclude the call",
            constraints=[
                "Do not rush the customer",
                "Thank them for their time"
            ],
            suggested_phrases=[
                "如果有任何问题，随时联系我，祝您生活愉快"
            ],
            exit_condition="Call is ended politely"
        ),
    }
    @classmethod
    def get(cls, state: CallState) -> PromptSpec:
        return cls.PROMPTS[state]