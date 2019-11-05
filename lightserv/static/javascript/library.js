var MYLIBRARY = MYLIBRARY || (function(){
    var _args = {}; // private

    return {
        init : function(Args) {
            _args = Args;
            // some other initialising
        },
        helloWorld : function() {
            alert('Hello World! -' + _args[0]);
        },

        swapTable : function(table_id) {
            $("#" + table_id).each(function() {
                var $this = $(this);
                var newrows = [];
                $this.find("tr").each(function(){
                    var i = 0;
                    $(this).find("td, th").each(function(){
                        i++;
                        if(newrows[i] === undefined) { newrows[i] = $("<tr></tr>"); }
                        if(i == 1)
                            newrows[i].append("<th>" + this.innerHTML  + "</th>");
                        else
                            newrows[i].append("<td>" + this.innerHTML  + "</td>");
                    });
                });
                $this.find("tr").remove();
                $.each(newrows, function(){
                    $this.append(this);
                
            });

            return false;
            });
        },

        defaultVertLayout : function(table_id) {
            $(document).ready(function(){
                $('table[id^=vertical]').each(function() {
                    var $this = $(this);
                    var newrows = [];
                    $this.find("tr").each(function(){
                        var i = 0;
                        $(this).find("td, th").each(function(){
                            i++;
                            if(newrows[i] === undefined) { newrows[i] = $("<tr></tr>"); }
                            if(i == 1)
                                newrows[i].append("<th>" + this.innerHTML  + "</th>");
                            else
                                newrows[i].append("<td>" + this.innerHTML  + "</td>");
                        });
                    });
                    $this.find("tr").remove();
                    $.each(newrows, function(){
                        $this.append(this);
                    });
                });

                return false;
                });
        } 
    };
}());