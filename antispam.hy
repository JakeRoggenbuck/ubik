(import collections [Counter])

(defn hello []
	"Hello, from Hy!")

(with [f (open "good.txt" "r")]
  (setv good_lines (.readlines f)))

(with [f (open "bad.txt" "r")]
  (setv bad_lines (.readlines f)))

(setv good_counter Counter)
(setv bad_counter Counter)

(defn create_map [lines counter]
    (for [line lines]
      (.update counter (.split line)))
    counter)

(defn make_maps []
  [(create_map good_lines good_counter) (create_map bad_lines bad_counter)])
