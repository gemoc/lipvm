class Environment:
    """
    Environment for interpreting a program.
    Language designer can dynamically set the attributes they need to keep track of.

    Example:

    - self._environment.attribute = value
    """

    # Making explicit the fact we use reflectivity to set the attributes of the environment (for debugging)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)

    def __getattr__(self, name):
        return super().__getattribute__(name)