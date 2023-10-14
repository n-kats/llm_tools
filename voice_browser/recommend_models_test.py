from unittest import TestCase, main
from voice_browser.recommend_models import RecommendState, ItemWithIndex, WaitingState


class ToyRecommender:
    def __init__(self, initail_text: str):
        self.__initial_text = initail_text

    def initial_state(self):
        return RecommendState(
            current_item=ItemWithIndex(
                f"0_0_0_{self.__initial_text}",
                play_index=0,
                group_index=0,
                recommendation_index=0,
            ),
            history=[],
            waiting_list={},
        )

    def next_state(self, state):
        selected_waiting_list = [
            item
            for item, waiting_state in state.waiting_list.items()
            if waiting_state.selected
        ]
        selected_waiting_list.sort(key=lambda item: item.priority)
        if selected_waiting_list:
            next_item = selected_waiting_list[0]
            return RecommendState(
                current_item=next_item,
                history=state.history + [state.current_item],
                waiting_list={
                    item: waiting_state
                    for item, waiting_state in state.waiting_list.items()
                    if item != next_item
                },
            )

        last_item = state.current_item
        next_play_index = last_item.play_index + 1
        n = next_play_index
        return RecommendState(
            current_item=ItemWithIndex(
                item=f"{n}_0_0_{self.__initial_text}",
                play_index=next_play_index,
                group_index=0,
                recommendation_index=0,
            ),
            history=state.history + [state.current_item],
            waiting_list={
                ItemWithIndex(
                    f"{n}_1_0_{self.__initial_text}",
                    play_index=next_play_index,
                    group_index=1,
                    recommendation_index=0,
                ): WaitingState(selected=True),
                ItemWithIndex(
                    f"{n}_1_1_{self.__initial_text}",
                    play_index=next_play_index,
                    group_index=1,
                    recommendation_index=1,
                ): WaitingState(selected=False),
                **state.waiting_list,
            },
        )


class RecommenderTest(TestCase):
    def test_foo(self):
        recommender = ToyRecommender("text")
        state = recommender.initial_state()
        for i in range(20):
            state = recommender.next_state(state)
            if i % 4 == 0 and state.waiting_list:
                edit_item = max(
                    state.waiting_list.keys(), key=lambda item: item.priority
                )
                state = state.update(edit_item, WaitingState(True))
            print(state.current_item.item)


if __name__ == "__main__":
    main()
