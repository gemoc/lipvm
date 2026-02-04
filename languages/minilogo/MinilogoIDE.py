from tkinter import *
from tkinter import ttk

from backend.lipvm import LipVM

class MinilogoIDE(Tk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title("Minilogo")
        self.geometry("800x600")

        self.components()
        self.layout()

        self._vm = LipVM("languages.minilogo")

    def components(self):
        self._panes = ttk.PanedWindow(self, orient=HORIZONTAL)

        self._code_pane = Frame(self._panes, bg="white")
        self._preview_pane = Frame(self._panes, bg="white")

        self._panes.add(self._code_pane, weight=1)
        self._panes.add(self._preview_pane, weight=1)

        self._code = Text(self._code_pane, width=1, height=1)

        self._canvas = Canvas(self._preview_pane, bg="white")
        self._buttons = Frame(self._preview_pane)

        self._start_button = Button(self._buttons, text="Run", command=self.start)
        self._step_forward_button = Button(self._buttons, text="Step forward", command=self.step_forward)

    def layout(self):
        # Main layout
        self._panes.pack(fill=BOTH, expand=True)

        # Code layout
        self._code.pack(fill=BOTH, expand=True)

        # Preview layout
        self._canvas.pack(fill=BOTH, expand=True)
        self._buttons.pack(fill=X, expand=False)

        # Buttons layout
        self._buttons.grid_rowconfigure(0, weight=1)

        self._buttons.grid_columnconfigure(0, weight=1)
        self._buttons.grid_columnconfigure(1, weight=1)

        self._start_button.grid(row=0, column=0, sticky='nesw')
        self._step_forward_button.grid(row=0, column=1, sticky='nesw')

    def code(self):
        return self._code.get('1.0', END)

    def start(self):
        self._vm.interpreter.interpret(self.code())
        self.draw()

    def step_forward(self):
        self._vm.interpreter.step()
        self.draw()

    def draw(self):
        self._canvas.delete("all")
        state = self._vm.interpreter.environment

        if hasattr(state, "lines"):
            for line in state.lines:
                self._canvas.create_line(
                    line[0][0],
                    line[0][1],
                    line[1][0],
                    line[1][1],
                    fill=line[2],
                    width=4
                )

if __name__ == '__main__':
    MinilogoIDE().mainloop()