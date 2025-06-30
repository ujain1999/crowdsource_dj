function isValidURL(str) {
  try {
    new URL(str);
    return true;
  } catch (e) {
    try{
        new URL("https://" + str);
        return true;
    }
    catch(e){
        return false;
    }
  }
}

const fetchData = () => {
    const inputValue = document.getElementById("search-or-url-input").value
    if (inputValue != ''){
        fetch("/api/search", {
            method: "POST",
            body: JSON.stringify({
                type : isValidURL(inputValue) ? "url" : "query",
                inputText : inputValue
            }),
            headers: {
                "Content-type": "application/json; charset=UTF-8"
            }
        })
        .then((response) => response.json())
        .then((data) => console.log(data));
    }
}

document.getElementById('search-btn').addEventListener('click', fetchData);