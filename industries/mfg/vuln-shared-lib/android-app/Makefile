.PHONY: test build ui-test clean
test:
	./gradlew :dealer-api-client:test :app:testDebugUnitTest
build:
	./gradlew assembleDebug assembleRelease
ui-test:
	./gradlew :app:connectedDebugAndroidTest
clean:
	./gradlew clean
