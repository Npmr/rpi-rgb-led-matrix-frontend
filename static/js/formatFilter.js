function filterFunction() {
    var checkBoxVertical = document.getElementById("checkbox-vertical");
    var checkBoxHorizontal = document.getElementById("checkbox-horizontal");
    var checkBoxSquare = document.getElementById("checkbox-square");

    const collectionVertical = document.getElementsByClassName('vertical');
    const collectionHorizontal = document.getElementsByClassName('horizontal');
    const collectionSqare = document.getElementsByClassName('square');

    console.log("im called");

    if (checkBoxVertical.checked == true) {
        for (let i = 0; i < collectionVertical.length; i++) {
            collectionVertical.item(i).style.display = "block";
        }
    } else {
        for (let i = 0; i < collectionVertical.length; i++) {
            collectionVertical.item(i).style.display = "none";
        }
    }

    if (checkBoxHorizontal.checked == true) {
        for (let i = 0; i < collectionHorizontal.length; i++) {
            collectionHorizontal.item(i).style.display = "block";
        }
    } else {
        for (let i = 0; i < collectionHorizontal.length; i++) {
            collectionHorizontal.item(i).style.display = "none";
        }
    }

    if (checkBoxSquare.checked == true) {
        for (let i = 0; i < collectionSqare.length; i++) {
            collectionSqare.item(i).style.display = "block";
        }
    } else {
        for (let i = 0; i < collectionSqare.length; i++) {
            collectionSqare.item(i).style.display = "none";
        }
    }
}