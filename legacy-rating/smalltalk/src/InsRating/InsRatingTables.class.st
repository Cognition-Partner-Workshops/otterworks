"
The shared flat-file rating tables, read in file order so that the first
matching row wins, exactly as the batch reads them.
"
Class {
	#name : 'InsRatingTables',
	#superclass : 'Object',
	#instVars : [ 'classRows', 'territoryRows', 'eligibilityRows', 'minimumRows', 'overrideRows' ],
	#category : 'InsRating',
	#package : 'InsRating'
}

{ #category : 'instance creation' }
InsRatingTables class >> fromDirectory: aDirectory [
	^ self new loadFrom: aDirectory asFileReference
]

{ #category : 'accessing' }
InsRatingTables >> classRows [ ^ classRows ]
{ #category : 'accessing' }
InsRatingTables >> eligibilityRows [ ^ eligibilityRows ]
{ #category : 'accessing' }
InsRatingTables >> minimumRows [ ^ minimumRows ]
{ #category : 'accessing' }
InsRatingTables >> overrideRows [ ^ overrideRows ]
{ #category : 'accessing' }
InsRatingTables >> territoryRows [ ^ territoryRows ]

{ #category : 'loading' }
InsRatingTables >> loadFrom: aDirectory [
	classRows := self rowsIn: aDirectory / 'class-factors.dat'.
	territoryRows := self rowsIn: aDirectory / 'territory-factors.dat'.
	eligibilityRows := self rowsIn: aDirectory / 'line-eligibility.dat'.
	minimumRows := self rowsIn: aDirectory / 'minimum-premium.dat'.
	overrideRows := self rowsIn: aDirectory / 'overrides.dat'
]

{ #category : 'loading' }
InsRatingTables >> rowsIn: aFile [
	^ (aFile contents lines
		reject: [ :each | each trimBoth isEmpty or: [ each first = $* ] ])
		collect: [ :each | (each splitOn: $|) collect: [ :field | field trimBoth ] ]
]

{ #category : 'dates' }
InsRatingTables >> row: aRow from: fromIndex inForceOn: aDate [
	"An empty end date leaves the row in force; both ends are inclusive."
	| to |
	to := (aRow size >= (fromIndex + 1) and: [ (aRow at: fromIndex + 1) notEmpty ])
		ifTrue: [ (aRow at: fromIndex + 1) asInteger ]
		ifFalse: [ 99999999 ].
	^ (aRow at: fromIndex) asInteger <= aDate and: [ aDate <= to ]
]
