import notes
from copy import deepcopy
for user in [None,7,8,9]:
 for note_id in [1,2,999]:
  before=deepcopy(notes.NOTES)
  try:
   expected=notes.read_note(user,note_id)
  except (PermissionError,KeyError) as error:
   try: notes.update_note(user,note_id,'blocked')
   except (PermissionError,KeyError) as actual:
    assert type(actual) is type(error) and actual.args==error.args
   else: raise AssertionError('accepted forbidden update')
   assert notes.NOTES==before
  else:
   updated=notes.update_note(user,note_id,'allowed')
   assert updated=={'owner':user,'text':'allowed'}
   updated['text']='external mutation'
   assert notes.NOTES[note_id]['text']=='allowed'
  notes.NOTES.clear();notes.NOTES.update(before)
print('PASS: 12 authorization/missing-note combinations; denied-state preservation; detached returns')
