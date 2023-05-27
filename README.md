# Python Debugger

<br>

## 1. 학습 계기
지금까지 각 언어가 크게 Compile, Interpreting의 2가지 방식으로 실행되는 것이 신기했습니다. <br>
**그 중 이벤트 단위로 변수, 실행 함수 스택의 추적이 흥미로울 것 같아 Python으로 디버깅을 공부하게 되었습니다.**

<br>

## 2. 잠시 짚고 가자! Compile과 Interpreting의 특징과 장점은?
#### ① Compile
- Runtime 전에 코드 분석 및 컴파일 과정이 필수!
- 미리 코드를 살펴보고 전체 맥락에 대한 정보가 주어지기 때문에 코드 최적화 및 성능 개선에 유리

<br>

#### ② Interpreting
- Runtime에 코드가 읽힘과 동시에 실행!
- Compile 언어와 다르게 코드 단위로 분리하여 디버깅 하는 게 상대적으로 용이하다

<br>

## 3. Class 상속 관계
#### 추적 함수의 정보를 모으는 classes

|관계|Class name|설명|
|:-|:-|:-|
|부모|Stack Inspector|추적 함수의 실행 스택을 검사|
||Tracer|추적 함수의 전역/local 변수 들을 저장하고 변화 추이를 저장|
||Collector|추적 함수 실행 동안에 발생하는 이벤트(line change, function call, function return 등) 기록 <br> 정확히는, 하위 class에서 활용할 수 있는 interface 제공|
|자식|Coverage Collector|추적 함수가 실행되는 context 정보(현재 실행 중인 함수 이름, 소스 코드 번호, 내부 변수 등)를 기록|

<br>

#### 추적 함수의 잘못된 부분을 탐지하는 classes

<br>

|관계|Class name|설명|
|:-|:-|:-|
|부모|Statistical Debugger|Collector를 활용하여 수집한 정보를 표 형태로 볼 수 있도록 도와줌|
||Difference Debugger|추적 함수의 문제 발생 여부에 따라 표 형태를 구분할 수 있도록 도와줌|
||Spectrum Debugger|추적 함수의 어떤 소스 코드에서 문제가 발생했는지 코드 레벨에서 보여줄 수 있도록 interface를 제공해주는 class|
|자식|Discrete Spectrum Debugger|추적 함수의 소스 코드의 문제 여부를 코드 시각화 및 색깔로 표현해주는 class|

##### Discrete Spectrum Debugger 활용 예시
<img width="817" alt="12345" src="https://github.com/Moon-GD/python-debugger/assets/74173976/16dce9a7-a270-418e-9a91-2b0d7fbd44f2">

**추적 관련 class 상속 + 수학 Metric을 활용하여 Tarantula Debugger와 Ochiai Debugger를 생성하는 것이 최종 목표**

<br>

## 4. 참고 자료
##### <a href="https://www.debuggingbook.org/">Debugging Book Organization</a>
