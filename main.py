import sys 

from core.lesp import listen

def main(arguments: list):
    if len(arguments) > 1:
        listen(arguments[1])
    else:
        listen()

if __name__ == '__main__':
    main(sys.argv)
 