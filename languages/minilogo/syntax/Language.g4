grammar Language;

// == Define parser rules ==

// Expressions
variable: variableName=ID;
literal: variable | NUMBER;

expression:
    leftOperand=expression op=OPERATOR rightOperand=expression
    | literal
    | LPAREN expression RPAREN;

// Function calls
arguments: expression (',' expression)*;

halt: 'halt' LPAREN RPAREN;
move: 'move' LPAREN x=expression ',' y=expression RPAREN;
color: 'color' LPAREN code=COLOR RPAREN;
pen: 'pen' LPAREN status=('up'|'down') RPAREN;

call: functionName=ID LPAREN args=arguments? RPAREN;

// Function definition
def: 'def' functionName=ID LPAREN params=parameters? RPAREN body;
parameters: variableName=ID (',' variableName=ID)*;

body: LCBRACKET (assignment | call | move | color | pen | halt | forloop | COMMENT)* RCBRACKET;

// Variable definition
assignment: variableName=ID '=' value=expression;

// Control structures
forloop
  : 'for' assignment 'to' end=expression body
  | 'for' variable 'to' end=expression body
  ;

// Main rule
main: (assignment | def | call | move | color | pen | halt | forloop | COMMENT)*;

// == Define lexer rules ==
ID : [a-zA-Z][a-zA-Z0-9]*;
NUMBER: '-'?[0-9]+;

OPERATOR: '+' | '-' | '*' | '/';

LPAREN : '(' ;
RPAREN : ')' ;
LCBRACKET: '{';
RCBRACKET: '}';

HEX: '0'..'9' | 'a'..'f' | 'A'..'F';
COLOR: '#' (HEX HEX HEX | HEX HEX HEX HEX HEX HEX);

WS: [ \t\r\n]+ -> skip;
COMMENT: ('//') ~( '\r' | '\n' )* -> channel(HIDDEN);
