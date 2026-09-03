package rules_test

import "testing"

func TestConditionOrder(t *testing.T) {
	cases := []struct {
		name string
		src  string
		want int
	}{
		// A numbered list item is what the tool reads as an instruction.
		{"the condition comes after the command",
			"1. Set the switch to NORMAL when the light comes on.\n", 1},
		{"the condition comes first",
			"1. When the light comes on, set the switch to NORMAL.\n", 0},
		{"an \"if\" condition after the command",
			"1. Disconnect the drive from the gearbox if it does not operate correctly.\n", 1},
		{"an \"if\" condition first",
			"1. If the drive does not operate correctly, disconnect it from the gearbox.\n", 0},

		// "check if" is an object of the verb, and not a condition.
		{"a clause verb takes the \"if\"",
			"1. Check if the valve is open.\n", 0},
		{"a clause verb with more words",
			"1. Verify if the pressure of the tank is correct.\n", 0},

		// A time phrase with no verb of its own is not a condition.
		{"a time phrase and no clause",
			"1. Close the valve after the test.\n", 0},

		// The rule reads an instruction only.
		{"descriptive text keeps its order",
			"The tool writes the report when the run is complete.\n", 0},
		{"a note keeps its order",
			"1. **NOTE:** The tool writes the report when the run is complete.\n", 0},

		// A condition word too near the start is part of the first phrase.
		{"a short first phrase",
			"1. Start if the light is on.\n", 0},

		// A condition that follows an infinitive belongs to it.
		{"an infinitive takes the condition",
			"1. Use the flag to read the report and to stop when you have enough.\n", 0},
		{"a value in capital letters is not an infinitive",
			"1. Set the switch to NORMAL when the light comes on.\n", 1},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := findingsOf(t, tc.src, "STE-5.4"); len(got) != tc.want {
				t.Errorf("got %d findings, want %d: %+v", len(got), tc.want, got)
			}
		})
	}
}
