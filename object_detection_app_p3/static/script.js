'use strict';

function isEmpty(guess) {
     if (guess>=0.0&&guess<=1.0) {
    alert(`threshold value is ${guess}`);
    }
    }


        document.querySelector('.sub').addEventListener('click', function () {
            const guess = Number(document.querySelector('.trsVal').value);
             isEmpty(guess) 
            console.log(guess, typeof guess);
        });
        
document.querySelector('.trbtn').addEventListener('click', function () {
    const va = (document.querySelector('.trbtn').value);
    console.log(va, typeof va);
});