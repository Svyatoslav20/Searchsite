const input = document.querySelector('.search__input')
const btn = document.querySelector('.search__button')
const select = document.querySelector('.search__select')

btn.addEventListener('click', submitRequest)

function submitRequest(event) {
    event.preventDefault()
    const value = input.value
    const selectValue = select.value
    let params;
    if(value) {
        if(selectValue === 'google' || selectValue === 'bing') {
            params = 'search?q='
        } else if(selectValue === 'yandex') {
            params = 'search?text='
        } else if(selectValue ==='duckduckgo') {
            params = '?q='
        }
        window.location.href = `https://www.${selectValue}.com/${params}` + value;
    }
}