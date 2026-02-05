grammar Language;

// == Define parser rules ==

machine: 'statemachine' name=ID;

events: 'events' (name=ID)*;

initial: 'initialState' name=ID;

state: 'state' name=ID transitions=transition* activate=function? 'end';

transition: name=ID '=>' stateName=ID;

function: 'activate:' body;

// Expressions
variable: variableName=ID;
literal: variable | NUMBER | STRING;

expression:
    leftOperand=expression op=OPERATOR rightOperand=expression
    | literal
    | LPAREN expression RPAREN;

// Function definition and call
arguments: expression (',' expression)*;
call: functionName=ID LPAREN args=arguments? RPAREN;

halt: 'halt' LPAREN RPAREN;
body: LCBRACKET (assignment | call | halt | forloop)* RCBRACKET;

// Variable definition
assignment: variableName=ID '=' value=expression;

// Control structures
forloop
  : 'for' assignment 'to' end=expression body
  | 'for' variable 'to' end=expression body
  ;

// Main rule
main: machine events initial state*;

// == Define lexer rules ==
ID : [a-zA-Z][a-zA-Z0-9]*;
NUMBER: '-'?[0-9]+;
STRING : '"' .*? '"' ;

OPERATOR: '+' | '-' | '*' | '/';

LPAREN : '(' ;
RPAREN : ')' ;
LCBRACKET: '{';
RCBRACKET: '}';

WS: [ \t\r\n]+ -> skip;
