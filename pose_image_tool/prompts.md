# 테스트에 쓴 프롬프트 모음

## 공통 포즈 서술 (모든 프롬프트에 이어붙임)
```
full body shot, dynamic acrobatic dance pose, bent sharply forward at the waist,
head tucked down between the legs, one arm raised straight overhead reaching upward with fingers spread,
the other arm wrapped tightly around a bent knee lifted up toward the chest,
balancing on one bare foot on tiptoe, muscular contorted twisting body, dramatic dance photography
```

## 최종본 (samples/output_01~03.png, steps=25, cfg=4)
1. `A young woman ballet dancer in a flowing red dress, {공통 포즈 서술}, dramatic stage lighting`
2. `An elderly man in a tailored suit, {공통 포즈 서술}, dramatic black and white fine art photography`
3. `A futuristic humanoid robot made of chrome metal, {공통 포즈 서술}, dramatic rim lighting, cinematic sci-fi photography`

negative prompt: 빈 문자열 (`""`)

## 실패했던 첫 시도 (steps=12, cfg=4) — 참고용
1. `A young woman ballet dancer in a flowing red dress, dramatic stage lighting, professional dance photography`
2. `An elderly man in a business suit, dramatic black and white studio photography, fine art portrait`
3. `A futuristic robot figure made of chrome metal, dramatic rim lighting, cinematic sci-fi photography`

→ 자세를 말로 서술하지 않고 `portrait`/`fine art portrait` 같은 정적 구도 단어만 넣었더니, 포즈 조건이 거의 무시되고 평범한 정면 인물사진이 나왔다. 이후 자세를 직접 서술하는 방식으로 바꿔서 해결했다.
