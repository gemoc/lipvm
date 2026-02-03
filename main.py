from sys import argv
from backend.lipvm import LipVM

def main(arguments: list):
    vm = LipVM(arguments[1])
    vm.serve(8080)

if __name__ == '__main__':
    main(argv)