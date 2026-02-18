(import collections [Counter])

(defn hello []
	"Hello, from Hy!")

(with [f (open "good.txt" "r")]
  (setv good_lines (.readlines f)))

(with [f (open "bad.txt" "r")]
  (setv bad_lines (.readlines f)))

(setv good_counter (Counter))
(setv bad_counter (Counter))

(defn create_map [lines counter]
    (for [line lines]
      (.update counter (.split line)))
    counter)

(defn make_maps []
  [(create_map good_lines good_counter) (create_map bad_lines bad_counter)])

(defn r_good [w]
  (min 1 (* 2 (/ (get good_counter w) (len good_counter)))))

(defn r_bad [w]
  (min 1 (/ (get bad_counter w) (len bad_counter))))

(defn p_spam [w]
  (max 0.01
       (min 0.99 (/
                    (r_bad w)
                    (+
                      (r_bad w)
                      (r_good w))))))

;; P.G. has a specific algorithm, but I'm going to try average

;; (defn classify_message [message]
;;   (setv words (.split message)
;;       scores words)
;;   (list scores))
