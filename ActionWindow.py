import debugging

class ActionWindow:
    def __init__(self):

        self.options = [
            Option("Date", "D"),
            Option("Attending Member", "A"),
            Option("Absent Member", "B"),
            Option("Other Member", "O"),
            Option("Topic", "T"),
            Option("Topic Description", "R"),
            Option("Nothing", "_")
        ]

    def displayOptions(self):
        for option in self.options:
            print(str(option))

    def askAction(self):
        self.displayOptions()
        print()
        return input("What is the above line?\n")

        


class Option():
        def __init__(self, option_description:str, option_button:"str"):
            self.description = option_description
            self.button = option_button

        def __str__(self):
            return "(" + self.button + ") " + self.description