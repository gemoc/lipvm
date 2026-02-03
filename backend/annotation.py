def step(visit_method):
    """
    Function to use as a decorator for visit methods in a LanguageVisitorImpl class.
    :param visit_method: a visit method decorated with @step.
    :return: a wrapper function that annotates the node in argument to add the stepNode = True attribute.
    """
    def wrapper(*args, **kwargs):
        args[1].stepNode = True
        return visit_method(*args, **kwargs)
    return wrapper
