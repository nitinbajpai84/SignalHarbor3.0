from sh_platform.speech import status


def test_speech_stays_off_in_production_unless_the_owner_switches_it_on():
    env = {"GOOGLE_API_KEY": "k"}
    assert status(env, "prod")["provider"] is None
    assert status(env | {"SH_SPEECH_IN_PROD": "1"}, "prod")["provider"] == "gemini"
    assert status({"SH_SPEECH_IN_PROD": "1"}, "prod")["provider"] is None  # still needs the key
